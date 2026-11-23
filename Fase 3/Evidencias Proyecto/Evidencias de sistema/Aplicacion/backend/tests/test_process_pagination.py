from test_access import tenants, as_user


def test_pagination_preserves_legacy_scopes_and_filters(client, tenants):
    legacy = client.get('/api/procesos').json()
    assert isinstance(legacy, list)
    expected = [r['id'] for r in legacy]
    first = client.get('/api/procesos/pagina?limit=1')
    assert first.status_code == 200 and first.headers['cache-control'] == 'no-store'
    data = first.json()
    assert data['total'] == len(expected) and data['items'][0]['id'] == expected[0]
    second = client.get('/api/procesos/pagina?limit=1&offset=1').json()
    assert second['items'][0]['id'] == expected[1]
    assert client.get('/api/procesos/pagina?offset=99999').json()['has_more'] is False
    assert client.get('/api/procesos/pagina', params={'cuba_id': tenants['foreign']['cube']}).status_code == 404
    assert client.patch('/api/procesos/1/finalizar').status_code == 200
    assert [r['id'] for r in client.get('/api/procesos/pagina?grupo=cerrados').json()['items']] == [1]
    assert 1 not in [r['id'] for r in client.get('/api/procesos/pagina?grupo=activos').json()['items']]
    as_user(client, tenants['stranger'])
    assert [r['id'] for r in client.get('/api/procesos/pagina').json()['items']] == [tenants['foreign']['process']]


def test_invalid_pagination_and_missing_identity(client):
    for query in ('limit=101', 'limit=0', 'offset=-1', 'grupo=invalid', 'cuba_id=0'):
        assert client.get('/api/procesos/pagina?' + query).status_code == 422
    client.headers.pop('Authorization')
    assert client.get('/api/procesos/pagina').status_code == 401
