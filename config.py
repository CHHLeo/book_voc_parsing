import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_RECORD_QUERIES = True
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    # MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    # MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_USERNAME = 'chhsieh.leo@gmail.com'
    MAIL_PASSWORD = '21070527crab'
    FLASKY_MAIL_SUBJECT_PREFIX = '[Flasky]'
    FLASKY_MAIL_SENDER = 'Flasky Admin <chhsieh.leo@gmail.com>'
    FLASKY_ADMIN = os.environ.get('FLASKY_ADMIN')
    FLASKY_POSTS_PER_PAGE = 20
    FLASKY_FOLLOWERS_PER_PAGE = 50
    FLASKY_COMMENTS_PER_PAGE = 30
    FLASKY_SLOW_DB_QUERY_TIME = 0.5
    PRESERVE_CONTEXT_ON_EXCEPTION = False

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    user_name = 'ch2leo'
    password = '21070527'
    database_host_address = 'ch2leo.mysql.pythonanywhere-services.com'
    database_name = 'ch2leo$americanyoudao'
    py_url = 'mysql://' + user_name + ':' + password + '@' + database_host_address + '/' + database_name + '?charset=utf8'
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
    #                           'mysql://root:@localhost/AmericanYouDao?charset=utf8'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or py_url

    # SQLALCHEMY_BINDS = {
    #     'Collins': 'mysql://root:@localhost/collins?charset=utf8',
    #     'Coca': 'mysql://root:@localhost/AmericanYouDao?charset=utf8'
    # }


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'data-test.sqlite')
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'data.sqlite')


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,

    'default': DevelopmentConfig
}
