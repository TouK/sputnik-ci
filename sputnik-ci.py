#!/usr/bin/python

import logging, os, subprocess, sys, urllib, zipfile

sputnik_version='1.6.1'


def configure_logger():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)


class CIVariables(object):
    def __init__(self, ci_service_name=None, ci=None, ci_name=None, pull_request_number=None, repo_slug=None, api_key=None):
        self.ci_service_name = ci_service_name
        self.ci = ci
        self.ci_name = ci_name
        self.pull_request_number = pull_request_number
        self.repo_slug = repo_slug
        self.api_key = api_key

    def is_set_every_required_env(self):
        return self.ci_service_name is not None and self.ci is not None and self.ci_name is not None \
               and self.pull_request_number is not None and self.repo_slug is not None

    def is_pull_request_initiated(self):
        pull_request_initiated = self.ci == 'true' and self.ci_name == 'true' and self.pull_request_number != "false"
        if not pull_request_initiated:
            logging.info('Stop processing as pull request has not been initiated')
        return pull_request_initiated


def get_env(single_env):
    try:
        assert (os.environ[single_env])
        return os.environ[single_env]
    except Exception:
        logging.debug("Problem while reading env variable: " + single_env)
        return None


def detect_ci_service_name():
    if get_env('TRAVIS'):
        return 'TRAVIS'
    elif get_env('CIRCLECI'):
        return 'CIRCLECI'
    else:
        return None


def check_required_env_variables(required_vars):
    logging.info("Check required env variables: " + str(required_vars))
    for env_var in required_vars:
        if get_env(env_var) is None:
            logging.error("Env variable " + env_var + " is required to run sputnik")
            return False
    return True


def init_travis_variables(ci_variables):
    ci_variables.ci = get_env("CI")
    ci_variables.ci_name = get_env("TRAVIS")
    ci_variables.pull_request_number = get_env("TRAVIS_PULL_REQUEST")
    ci_variables.repo_slug = get_env("TRAVIS_REPO_SLUG")


def init_circleci_variables(ci_variables):
    ci_variables.ci = get_env("CI")
    ci_variables.ci_name = get_env("CIRCLECI")
    ci_variables.pull_request_number = get_env("CIRCLE_PR_NUMBER")
    ci_variables.repo_slug = get_env("CIRCLE_PROJECT_USERNAME") + '/' + get_env("CIRCLE_PROJECT_REPONAME")


def init_variables():
    ci_variables = CIVariables()
    ci_variables.ci_service_name = detect_ci_service_name()
    if ci_variables.ci_service_name == 'TRAVIS':
        init_travis_variables(ci_variables)
    elif ci_variables.ci_service_name == 'CIRCLECI':
        init_circleci_variables(ci_variables)

    ci_variables.api_key = get_env("api_key")
    return ci_variables


def unzip(zip):
    zip_ref = zipfile.ZipFile(zip, 'r')
    zip_ref.extractall(".")
    zip_ref.close()


def download_file(url, file_name):
    logging.info("Downloading " + file_name)
    try:
        urllib.urlretrieve(url, filename=file_name)
    except Exception:
        logging.error("Problem while downloading " + file_name + " from " + url)


def download_files_and_run_sputnik(ci_variables):
    if ci_variables.is_pull_request_initiated():
        if ci_variables.api_key:
            configs_url = "http://sputnik.touk.pl/conf/" + ci_variables.repo_slug + "/configs?key=" + ci_variables.api_key
            download_file(configs_url, "configs.zip")
            unzip("configs.zip")

        global sputnik_version
        sputnik_jar_url = "http://repo1.maven.org/maven2/pl/touk/sputnik/" + sputnik_version + "/sputnik-" + sputnik_version + "-all.jar"
        logging.debug('Sputnik jar url: ' + sputnik_jar_url)
        download_file(sputnik_jar_url, "sputnik.jar")

        subprocess.call(['java', '-jar', 'sputnik.jar', '--conf', 'sputnik.properties', '--pullRequestId',
                         ci_variables.pull_request_number, '--apiKey', ci_variables.api_key])

def sputnik_ci():
    configure_logger()
    ci_variables = init_variables()

    if ci_variables.is_set_every_required_env():
        download_files_and_run_sputnik(ci_variables)


sputnik_ci()
