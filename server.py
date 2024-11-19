import os
from flask import Flask, request
from bp.celery import make_celery
from bp.auth import auth
from bp.routes import routes
import logging
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1, x_port=1, x_prefix=1)
    app.config.update(
        broker_url='redis://redis:6379/0',
        result_backend='redis://redis:6379/0',
        include=['bp.tasks']
    )
    app.logger.setLevel(logging.INFO)
    celery = make_celery(app)

    #config env variables
    os.environ['SECRET_KEY'] = os.urandom(12).hex()
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

    @app.before_request
    def log_request_info():
        if not request.path.startswith('/static/media/') and request.remote_addr != "127.0.0.1":
            app.logger.info("-" * 110)
            app.logger.info('--- REQUEST --- ')
            app.logger.info('Mimetype: %s', request.mimetype)
            if (len(request.get_data()) < 2 ** 15):
                app.logger.info('Body: %s', request.get_data())
            else:
                if request.mimetype == 'application/json':
                    app.logger.info('JSON: %s', request.json)
                else:
                    app.logger.info('Form: %s', request.form)

            app.logger.info('Cookies: %s', request.cookies)

    @app.after_request
    def log_response(response):
        if not request.path.startswith('/static/media/') and request.remote_addr != "127.0.0.1":
            try:
                app.logger.info('--- RESPONSE --- ')
                app.logger.info('Status: %s', response.status)
                app.logger.info('Cookies set: %s', response.headers.getlist("Set-Cookie"))
                app.logger.info('Body: %s', response.get_data())
            except Exception:
                app.logger.info("Can't display response.")
            app.logger.info("-" * 110)
        return response

    app.celery = celery
    app.register_blueprint(auth)
    app.register_blueprint(routes)
    return app, celery

app, celery = create_app()

if __name__ == "__main__":
    host = os.getenv('HOST', "0.0.0.0")
    port = int(os.getenv('PORT', 5050))
    app.run(host=host, port=port)
