import hmac
import json
import hashlib
import io
import logging
import os
from pathlib import Path
import secrets
import socket
import threading
import time
import zipfile
from flask import Flask, abort, jsonify, request, send_file
from waitress import create_server
from . import APP_ID, VERSION
from .paths import InstanceLock, atomic_json, owned_root
from .store import Store

PRODUCT = Path(__file__).resolve().parent.parent
WEB_FILES = {'index.html','app.css','app.js','skills.js','seo.html','seo.css','seo.js'}
DEMO_FILES = {'preview.html','preview.css','preview.js','fixtures.js','skills.js','seo.html','seo.css','seo.js'}

def create_app(store, port, instance, control_token, stopping):
    app = Flask(__name__, static_folder=None)
    app.config.update(TRUSTED_HOSTS=['127.0.0.1'], MAX_CONTENT_LENGTH=1024)
    expected_host = f'127.0.0.1:{port}'

    @app.before_request
    def boundary():
        if request.host != expected_host or request.remote_addr != '127.0.0.1':
            abort(400)
        origin = request.headers.get('Origin')
        if origin and origin != f'http://{expected_host}':
            abort(403)
        if request.headers.get('Sec-Fetch-Site') == 'cross-site':
            abort(403)

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
                                 'Referrer-Policy':'no-referrer', 'X-Frame-Options':'SAMEORIGIN',
                                 'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"})
        return response

    @app.get('/health')
    def health():
        return jsonify(app=APP_ID, version=VERSION, instance=instance, status='running')

    @app.get('/api/<section>')
    def state(section):
        if section not in {'automation','seo','skills','onboarding','tickets'}:
            abort(404)
        try:
            return jsonify(store.snapshot(section))
        except Exception as error:
            app.logger.error('record_read_failed: %s', type(error).__name__)
            return jsonify(error='record_read_failed', message='本机记录读取失败，不能当作空库或零数据。'), 503

    @app.get('/')
    def home():
        return send_file(PRODUCT/'web/index.html')

    @app.get('/assets/<name>')
    def asset(name):
        if name not in WEB_FILES:
            abort(404)
        return send_file(PRODUCT/'web'/name)

    @app.get('/downloads/luxixi-workbench.zip')
    def skill_download():
        bundle=PRODUCT/'downloads/luxixi-workbench.zip'
        if bundle.is_file():return send_file(bundle,as_attachment=True,download_name='luxixi-workbench.zip',mimetype='application/zip')
        # Installed Skill runtime: rebuild only its verified package whitelist, never .venv/data.
        skill=PRODUCT.parents[1];manifest=skill/'bundle-manifest.json'
        if not manifest.is_file():abort(404)
        try:
            entries=json.loads(manifest.read_text(encoding='utf-8'))['files'];stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for item in entries:
                    file=skill/item['path']
                    if file.is_symlink() or not file.resolve().is_relative_to(skill.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('package changed')
                    archive.writestr('luxixi-workbench/'+item['path'],file.read_bytes())
                archive.writestr('luxixi-workbench/bundle-manifest.json',manifest.read_bytes())
            stream.seek(0)
            return send_file(stream,as_attachment=True,download_name='luxixi-workbench.zip',mimetype='application/zip')
        except (OSError,ValueError,KeyError):abort(404)

    @app.get('/demo/')
    @app.get('/demo/<name>')
    def demo(name='preview.html'):
        if name not in DEMO_FILES:
            abort(404)
        return send_file(PRODUCT/'demo'/name)

    @app.post('/_control/stop')
    def stop():
        supplied = request.headers.get('Authorization', '')
        if not hmac.compare_digest(supplied, 'Bearer ' + control_token):
            abort(403)
        threading.Timer(.2, stopping.set).start()
        return jsonify(stopping=True)

    @app.errorhandler(404)
    def missing(_error):
        return jsonify(error='not_found'), 404
    return app

def serve(data_dir, port):
    if not 1024 <= port <= 65535:
        raise ValueError('端口必须在1024至65535之间')
    root = owned_root(data_dir, create=True)
    lock = InstanceLock(root)
    instance = secrets.token_hex(16)
    server = None
    listener = None
    try:
        lock.acquire()
        store = Store(root)
        stopping = threading.Event()
        token = secrets.token_urlsafe(32)
        app = create_app(store, port, instance, token, stopping)
        address={'host':'127.0.0.1','port':port}
        if os.name=='nt':
            # Waitress sets SO_REUSEADDR by default, which can share an occupied
            # Windows port. Bind exclusively first, using its public sockets API.
            listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            listener.bind(('127.0.0.1',port))
            address={'sockets':[listener]}
        server = create_server(app, **address, threads=4,
                               clear_untrusted_proxy_headers=True, max_request_body_size=1024)
        atomic_json(root/'service-config.json', {'app':APP_ID,'schema':1,'port':port})
        atomic_json(root/'runtime.json', {'app':APP_ID,'instance':instance,'pid':os.getpid(),'port':port,'token':token})
        http_done = threading.Event()
        def run_http():
            try:
                server.run()
            except BaseException:
                app.logger.exception('HTTP service thread failed')
            finally:
                http_done.set()
        threading.Thread(target=run_http, daemon=True).start()
        while not stopping.wait(.2):
            if http_done.is_set():
                raise RuntimeError('HTTP服务意外结束，已清理本实例；请检查独立日志')
    finally:
        if server:
            server.close()
            server.task_dispatcher.shutdown(timeout=2)
        elif listener:
            listener.close()
        runtime = root/'runtime.json'
        if runtime.exists():
            try:
                if json.loads(runtime.read_text(encoding='utf-8')).get('instance') == instance:
                    runtime.unlink()
            except (ValueError, OSError):
                pass
        lock.close()
