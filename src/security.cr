require "kemal-basic-auth"

# Key the rate limiter by source IP, never the ephemeral TCP port.
class KVBasicAuthHandler < Kemal::BasicAuth::Handler
  private def remote_key(context) : String?
    address = context.request.remote_address
    case address
    when Socket::IPAddress
      address.address
    else
      address.try(&.to_s)
    end
  end
end

module KVSecurity
  MAX_JSON_BYTES = 65_536

  def self.read_json_body(body : IO?) : String
    return "{}" unless body
    result = IO::Memory.new
    bytes = IO.copy(body, result, MAX_JSON_BYTES + 1)
    raise "Request body too large" if bytes > MAX_JSON_BYTES
    result.to_s
  end
end

# Apply headers before authentication, baked assets and application endpoints.
class KVSecurityHandler < Kemal::Handler
  def call(context)
    headers = context.response.headers
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Frame-Options"] = "DENY"
    headers["Referrer-Policy"] = "no-referrer"
    headers["Cross-Origin-Resource-Policy"] = "same-origin"
    headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    headers["Cache-Control"] = "no-store"
    request = context.request
    if request.method != "GET" && request.method != "HEAD"
      origin = request.headers["Origin"]?
      host = request.headers["Host"]?
      unless origin && host && (origin == "http://#{host}" || origin == "https://#{host}")
        context.response.status_code = 403
        context.response.print "Origin rejected"
        return
      end
    end
    call_next(context)
  end
end
