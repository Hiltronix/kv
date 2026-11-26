#!/usr/bin/env python3
"""Compare installed Alpine source package versions with published security fixes."""
import os
import sys
import traceback
import hashlib
import json
import subprocess
from pathlib import Path


def AuditPackages(databasePaths, installedPath):

    fixedVersions = {}
    databaseInfo = []
    for path in databasePaths:
        raw = path.read_bytes()
        databaseInfo.append({'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest()})
        database = json.loads(raw)
        for entry in database['packages']:
            package = entry['pkg']
            fixes = fixedVersions.setdefault(package['name'], {})
            for version, advisories in package.get('secfixes', {}).items():
                for advisory in advisories:
                    fixes.setdefault(advisory, set()).add(version)

    installed = []
    for record in installedPath.read_text().split('\n\n'):
        fields = {line[0]: line[2:] for line in record.splitlines()
                  if len(line) > 2 and line[1] == ':'}
        if 'P' in fields and 'V' in fields:
            installed.append((fields['P'], fields['V'], fields.get('o', fields['P'])))

    comparisons = {}
    findings = {}
    for package, version, source in installed:
        for advisory, versions in fixedVersions.get(source, {}).items():
            for fixed in versions:
                key = (version, fixed)
                if key not in comparisons:
                    comparisons[key] = subprocess.check_output(
                        ['apk', 'version', '-t', version, fixed], text=True).strip()
                if comparisons[key] == '<':
                    finding = findings.setdefault((source, version, advisory), {
                        'source': source, 'installed': version, 'advisory': advisory,
                        'packages': set(), 'fixVersions': set()
                    })
                    finding['packages'].add(package)
                    finding['fixVersions'].add(fixed)

    results = [{**finding, 'packages': sorted(finding['packages']),
                'fixVersions': sorted(finding['fixVersions'])}
               for _, finding in sorted(findings.items())]
    print(json.dumps({
        'scope': 'Installed Alpine build packages, not a complete runtime vulnerability assessment',
        'method': 'Installed source package version below a published fix version; applicability requires review',
        'databases': databaseInfo,
        'installedPackageCount': len(installed),
        'potentialFindings': results,
        'limitations': [
            'Security databases do not describe every affected version or unpublished vulnerability.',
            'Source-built libraries, Crystal shards and the target operating system are not covered.',
            'A finding can affect a build-only package rather than the final executable.'
        ]
    }, indent=2))


if __name__ == '__main__':
    try:
        AuditPackages([Path(path) for path in sys.argv[1:]], Path('/lib/apk/db/installed'))
    except Exception as e:
        trbk = f'Exception! {e.__class__.__name__}: {e}\n{traceback.format_exc()}'
        print(trbk, file=sys.stderr)
        sys.exit(1)
