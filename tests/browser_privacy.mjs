import { spawn } from 'node:child_process'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import assert from 'node:assert/strict'

const [executable, origin, username, password] = process.argv.slice(2)
const profile = await mkdtemp(join(tmpdir(), 'kv-browser-'))
const browser = spawn(executable, [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-background-networking',
  '--disable-component-update', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank'
], { stdio: 'ignore' })
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
let ws
try {
  let port
  for (let i = 0; i < 100; i++) {
    try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; break } catch {}
    await delay(100)
  }
  assert(port, 'Chrome did not start')
  const targets = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json()
  const page = targets.find(target => target.type === 'page')
  assert(page, 'No browser page target')
  ws = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true })
    ws.addEventListener('error', reject, { once: true })
  })
  let id = 0
  const pending = new Map()
  const requests = new Set()
  const responses = new Map()
  const sockets = []
  const socketUrls = new Map()
  let challenges = 0
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const requestId = ++id
    pending.set(requestId, { resolve, reject })
    ws.send(JSON.stringify({ id: requestId, method, params }))
  })
  ws.addEventListener('message', event => {
    const message = JSON.parse(event.data)
    if (message.id) {
      const entry = pending.get(message.id)
      pending.delete(message.id)
      if (entry) message.error ? entry.reject(new Error(JSON.stringify(message.error))) : entry.resolve(message.result)
      return
    }
    const p = message.params || {}
    if (message.method === 'Fetch.authRequired') {
      challenges++
      send('Fetch.continueWithAuth', { requestId: p.requestId, authChallengeResponse: challenges <= 4 ?
        { response: 'ProvideCredentials', username, password } : { response: 'CancelAuth' } }).catch(console.error)
    } else if (message.method === 'Fetch.requestPaused') {
      send('Fetch.continueRequest', { requestId: p.requestId }).catch(console.error)
    } else if (message.method === 'Network.requestWillBeSent') {
      requests.add(p.request.url)
    } else if (message.method === 'Network.responseReceived') {
      responses.set(p.response.url, p.response.status)
    } else if (message.method === 'Network.webSocketCreated') {
      socketUrls.set(p.requestId, p.url)
      requests.add(p.url)
    } else if (message.method === 'Network.webSocketHandshakeResponseReceived') {
      sockets.push({ url: socketUrls.get(p.requestId), status: p.response.status })
    }
  })
  await send('Network.enable')
  await send('Page.enable')
  await send('Fetch.enable', { handleAuthRequests: true })
  for (const path of ['/', '/mobile']) {
    const navigation = await send('Page.navigate', { url: origin + path })
    assert(!navigation.errorText, navigation.errorText)
    await delay(5000)
    assert.equal(responses.get(origin + path), 200, 'Page not loaded: ' + path)
  }
  for (const url of requests) {
    if (url.startsWith('data:') || url.startsWith('blob:') || url === 'about:blank') continue
    assert(url.startsWith(origin + '/') || url.startsWith(origin.replace('http:', 'ws:') + '/'), 'External page request: ' + url)
  }
  for (const path of ['/vendor/pico.min.css', '/vendor/fonts.css', '/vendor/Oxanium.ttf', '/vendor/MaterialIcons-Regular.ttf']) {
    assert.equal(responses.get(origin + path), 200, 'Local resource not loaded: ' + path)
  }
  assert(sockets.some(socket => socket.status === 101 && socket.url === origin.replace('http:', 'ws:') + '/ws/input'),
    'Browser did not establish authenticated input WebSocket')
  console.log('Desktop and mobile Chrome page requests stayed on the local KV origin; embedded assets and WebSocket verified.')
} finally {
  if (ws) ws.close()
  browser.kill('SIGTERM')
  await Promise.race([new Promise(resolve => browser.once('exit', resolve)), delay(3000)])
  await rm(profile, { recursive: true, force: true, maxRetries: 3 }).catch(() => {})
}
