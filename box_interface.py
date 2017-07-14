# coding: utf-8

from __future__ import print_function, unicode_literals

import bottle
import configparser
import webbrowser
from threading import Thread, Event
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server
from boxsdk import OAuth2


def authenticate(oauth_class=OAuth2, force_refresh=False):
    class StoppableWSGIServer(bottle.ServerAdapter):
        def __init__(self, *args, **kwargs):
            super(StoppableWSGIServer, self).__init__(*args, **kwargs)
            self._server = None

        def run(self, app):
            server_cls = self.options.get('server_class', WSGIServer)
            handler_cls = self.options.get('handler_class', WSGIRequestHandler)
            self._server = make_server(self.host, self.port, app, server_cls, handler_cls)
            self._server.serve_forever()

        def stop(self):
            self._server.shutdown()

    # Config setup
    cfg = configparser.ConfigParser()
    cfg.read('app.cfg')
    client_id = cfg['client_info']['client_id']
    client_secret = cfg['client_info']['client_secret']

    # Verify if there is a valid token already
    if 'app_info' in cfg and not force_refresh:
        access_token = cfg.get('app_info', 'access_token')
        refresh_token = cfg.get('app_info', 'refresh_token')

        oauth = oauth_class(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token
        )

        return oauth

    auth_code = {}
    auth_code_is_available = Event()

    local_oauth_redirect = bottle.Bottle()

    @local_oauth_redirect.get('/')
    def get_token():
        auth_code['auth_code'] = bottle.request.query.code
        auth_code['state'] = bottle.request.query.state
        auth_code_is_available.set()

    local_server = StoppableWSGIServer(host='localhost', port=8080)
    server_thread = Thread(target=lambda: local_oauth_redirect.run(server=local_server))
    server_thread.start()

    oauth = oauth_class(
        client_id=client_id,
        client_secret=client_secret,
    )
    auth_url, csrf_token = oauth.get_authorization_url('http://localhost:8080')
    webbrowser.open(auth_url)

    auth_code_is_available.wait()
    local_server.stop()
    assert auth_code['state'] == csrf_token
    access_token, refresh_token = oauth.authenticate(auth_code['auth_code'])

    print('access_token: ' + access_token)
    print('refresh_token: ' + refresh_token)

    if 'app_info' not in cfg:
        cfg['app_info'] = {}

    cfg['app_info']['access_token'] = access_token
    cfg['app_info']['refresh_token'] = refresh_token
    with open('app.cfg', 'w') as configfile:
        cfg.write(configfile)

    return oauth
