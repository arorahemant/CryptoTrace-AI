"""Opt-in live validation through authenticated intake and the normal case APIs.

Never imported by the application. Uses an isolated, temporary local database.
Only successful public RPC results and fixed failure codes enter the capture;
credentials, endpoints, authentication responses and headers are never stored.
"""
import argparse
import asyncio
import copy
import json
import logging
import os
from pathlib import Path
import tempfile
import time

ADDRESS = '0xd152f549545093347a162dce210e7293f1452150'
FROM_BLOCK, TO_BLOCK = 20000047, 20000355


async def validate(output):
    import httpx
    from app.core.config import settings
    from app.main import app
    from app.providers.alchemy import AlchemyEthereumProvider
    import app.services.investigation_service as service_module

    if not settings.ALCHEMY_API_KEY:
        raise RuntimeError('not_configured')
    responses, instances = [], []

    class RecordingProvider(AlchemyEthereumProvider):
        async def _send(self, method, params):
            entry = {'method': method, 'params': copy.deepcopy(params)}
            try:
                status, body, retry = await super()._send(method, params)
            except (asyncio.CancelledError, TimeoutError):
                responses.append({**entry, 'failure': 'timeout'})
                raise
            if status == 200 and 'result' in body:
                responses.append({**entry, 'result': copy.deepcopy(body['result'])})
            else:
                # Provider error messages can echo an endpoint. Never capture them.
                responses.append({**entry, 'failure': 'provider_limit' if status == 429 else 'unavailable'})
            return status, body, retry

    original_factory = service_module.get_provider

    def factory(chain):
        if chain != 'ethereum':
            raise RuntimeError('unexpected_chain')
        provider = RecordingProvider()
        instances.append(provider)
        return provider

    service_module.get_provider = factory
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://validation.local/api/v1', timeout=30) as client:
                async def call(method, path, payload=None):
                    response = await client.request(method, path, json=payload)
                    if response.status_code >= 400:
                        raise RuntimeError('validation_api_request_failed')
                    return response.json()

                # These accounts exist only in the disposable local demo-auth DB.
                auth = await call('POST', '/auth/login', {'username': 'investigator', 'password': 'investigate123'})
                client.headers['Authorization'] = 'Bearer ' + auth['access_token']
                case = await call('POST', '/cases', {'title': 'Benign public high-activity validation', 'reported_wallet': ADDRESS,
                    'blockchain': 'ethereum', 'asset': 'ETH', 'description': 'Public transfer-observation example. No ownership, wrongdoing or VASP attribution claim.'})
                path = '/cases/' + case['id']
                before = await call('GET', path)
                started = time.monotonic()
                run = await call('POST', path + '/investigate', {'from_block': FROM_BLOCK, 'to_block': TO_BLOCK, 'max_hops': 2, 'min_amount': 0, 'direction': 'outgoing'})
                elapsed = time.monotonic() - started
                graph = await call('GET', path + '/graph')
                transfers = await call('GET', path + '/transactions')
                findings = await call('GET', path + '/findings')
                evidence = await call('GET', path + '/evidence')
                recommendations = await call('GET', path + '/recommendations')
                report = await call('POST', path + '/report')
                coverage = run['capability']['coverage']
                assert not run['is_demo'] and run['capability']['data_origin'] == 'observed'
                assert len(graph['edges']) == len(transfers['transactions']) <= 100
                assert len(graph['nodes']) >= 50 and len(graph['edges']) >= 50, 'target_not_observed'
                assert not findings['findings'] and all(not n.get('vasp_name') for n in graph['nodes'])
                assert all(not tx['is_suspicious'] and tx['amount_precision'] == 'exact' for tx in transfers['transactions'])
                assert graph['run_id'] == run['run_id'] == report['capability']['run_id']
                summary = {'address': ADDRESS, 'network': 'Ethereum Mainnet', 'from_block': FROM_BLOCK, 'to_block': TO_BLOCK,
                    'nodes': len(graph['nodes']), 'events': len(graph['edges']), 'transactions': len({t['hash'] for t in transfers['transactions']}),
                    'requests': instances[0].requests, 'api_observation_seconds': round(elapsed, 3),
                    'coverage_state': coverage['state'], 'partial': coverage['partial'], 'provider_errors': coverage['provider_errors'],
                    'findings': len(findings['findings']), 'evidence': evidence['total'], 'recommendations': len(recommendations['recommendations'])}
                capture = {'description': 'Actual Alchemy Mainnet RPC responses and API output. Benign validation only; no wrongdoing or ownership inference. Not runtime frontend data.',
                    'summary': summary, 'responses': responses, 'graph': graph, 'transactions': transfers['transactions'],
                    'capability': run['capability'], 'intake_capability': before['capability'], 'report': report}
                serialized = json.dumps(capture, indent=2, ensure_ascii=True) + '\n'
                # Check the actual credential in memory; never print it on failure.
                key = settings.ALCHEMY_API_KEY.get_secret_value()
                if key in serialized or 'alchemy.com/v2/' in serialized or auth['access_token'] in serialized:
                    raise RuntimeError('capture_security_check_failed')
                output.write_text(serialized, encoding='utf-8')
                print(json.dumps(summary))
    finally:
        service_module.get_provider = original_factory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True, help='Explicitly allow the bounded live Alchemy run')
    parser.add_argument('--capture', type=Path, required=True, help='New JSON output file; existing files are never overwritten')
    args = parser.parse_args()
    if args.capture.exists():
        parser.error('Capture file already exists; choose a new output path')
    output = args.capture.resolve()
    if not output.parent.is_dir():
        parser.error('Capture parent directory must exist')
    # Set database/auth scope before importing the application singleton settings.
    with tempfile.TemporaryDirectory(prefix='cryptotrace-high-activity-') as directory:
        os.environ.update(DATABASE_URL='sqlite+aiosqlite:///' + str(Path(directory) / 'validation.db'), DEMO_MODE='true', APP_ENV='local', SEED_DEMO_ACCOUNTS='true')
        logging.disable(logging.CRITICAL)
        try:
            asyncio.run(validate(output))
        except Exception:
            # No exception text: transports and API errors can contain credentials.
            print('High-activity validation failed; no successful capture was written.')
            raise SystemExit(1) from None


if __name__ == '__main__':
    main()
