import logging
from uuid import UUID


def test_ids_correlate_without_leaking_request_data(client, caplog):
    caplog.set_level(logging.INFO, logger='mosto.requests')
    response = client.get('/api/health?password=secret-query', headers={
        'Authorization':'Bearer secret-token', 'X-Request-ID':'attacker-controlled'})
    ident = response.headers['x-request-id']
    assert str(UUID(ident)) == ident
    records = [r.getMessage() for r in caplog.records if r.name == 'mosto.requests']
    assert any(ident in line and 'status=200' in line for line in records)
    assert not any(word in '\n'.join(records) for word in ['secret-query','secret-token','attacker-controlled'])
    second = client.get('/api/health')
    assert second.headers['x-request-id'] != ident


def test_unauthorized_and_unknown_routes_are_correlated(client, caplog):
    caplog.set_level(logging.INFO,logger='mosto.requests')
    client.headers.pop('Authorization')
    denied=client.get('/api/procesos/pagina')
    assert denied.status_code==401 and denied.headers['x-request-id']
    missing=client.get('/private-path-secret')
    assert missing.status_code==404 and missing.headers['x-request-id']
    records='\n'.join(r.getMessage() for r in caplog.records if r.name=='mosto.requests')
    assert 'private-path-secret' not in records and 'route=unmatched' in records


def test_browser_can_read_correlation_header(client):
    response=client.get('/api/health',headers={'Origin':'http://localhost:5173'})
    assert 'X-Request-ID' in response.headers['access-control-expose-headers']
