import os
from flask import Flask, request, g
from bp.celery import make_celery
from bp.auth import auth
from bp.routes import routes
from bp.log_util import get_logger
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.middleware.profiler import ProfilerMiddleware
from bp.util import get_user
from config import REDIS_IP, SECRET_KEY


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1, x_port=1, x_prefix=1)
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app, profile_dir='profiler', restrictions=[5])
    app.config.update(
        broker_url=f'redis://{REDIS_IP}:6379/0',
        result_backend=f'redis://{REDIS_IP}:6379/0',
        include=['bp.tasks']
    )
    celery = make_celery(app)

    #config env variables
    # os.environ['SECRET_KEY'] = os.urandom(12).hex()
    app.config['SECRET_KEY'] = SECRET_KEY

    @app.before_request
    def log_request_info():
        if not request.path.startswith('/static/media/') and request.remote_addr != "127.0.0.1":
            try:
                user = g.user
            except AttributeError as e:
                user = {'username':'not logged in', '_id':'not logged in'}
            logger = get_logger(request.path)
            logger.info("-" * 80)
            logger.info('--- REQUEST --- ')
            logger.info('User: %s (%s)', user['username'], user['_id'])
            if (len(request.get_data()) < 2 ** 15):
                logger.info('Body: %s', request.get_data())
            else:
                if request.mimetype == 'application/json':
                    logger.info('JSON: %s', request.json)
                else:
                    logger.info('Form: %s', request.form)
            logger.info('Cookies: %s', request.cookies)

    @app.after_request
    def log_response(response):
        if not request.path.startswith('/static/media/') and request.remote_addr != "127.0.0.1":
            logger = get_logger(request.path)
            try:
                logger.info('--- RESPONSE --- ')
                logger.info('Status: %s', response.status)
                logger.info('Cookies set: %s', response.headers.getlist("Set-Cookie"))
                logger.info('Body: %s', response.get_data())
            except Exception:
                logger.info("Can't display response.")
            logger.info("-" * 80)
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
