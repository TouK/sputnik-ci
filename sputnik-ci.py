#!/usr/bin/python

import logging, os, subprocess, sys, zipfile, platform, re

try:
    from urllib.request import Request, urlopen, urlretrieve
    from urllib.error import HTTPError
    from urllib.parse import urlencode
except ImportError:
    from urllib2 import Request, urlopen, HTTPError
    from urllib import urlencode, urlretrieve

sputnik_version='1.10.1'
sputnik_base_url='https://sputnik.ci/'

if len(sys.argv) > 1:
    provider = sys.argv[1]
else:
    provider = 'github'


if len(sys.argv) > 2:
    sputnik_base_url = sys.argv[2]


def configure_logger():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)


class CIVariables(object):
    def __init__(self, ci_service_name=None, ci=None, ci_name=None, pull_request_number=None, repo_slug=None, api_key=None, build_id=None):
        self.ci_service_name = ci_service_name
        self.ci = ci
        self.ci_name = ci_name
        self.pull_request_number = pull_request_number
        self.repo_slug = repo_slug
        self.api_key = api_key
        self.build_id = build_id

    def is_set_every_required_env(self):
        return self.ci_service_name is not None and self.ci is not None and self.ci_name is not None \
               and self.pull_request_number is not None and self.repo_slug is not None and (self.api_key is not None or self.build_id is not None)

    def is_pull_request_initiated(self):
        pull_request_initiated = self.ci == 'true' and self.ci_name == 'true' and self.pull_request_number != "false"
        if not pull_request_initiated:
            logging.error('Stop processing as pull request has not been initiated')
        return pull_request_initiated

    def __str__(self):
        return "ci_name: " + self.ci_name + ", pr: " + self.pull_request_number + ", repo: " + self.repo_slug


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
    elif get_env('JENKINS_URL'):
        return 'JENKINS'
    elif get_env('GITLAB_CI'):
        return 'GITLAB_CI'
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
    ci_variables.build_id = get_env("TRAVIS_BUILD_ID")


def get_circleci_pr_number(repo_slug):
    pr_from_fork = get_env("CIRCLE_PR_NUMBER")
    pr_number = None
    if pr_from_fork is None:
        pull_requests_str = get_env("CI_PULL_REQUESTS")
        if pull_requests_str is not None:
            pull_request_url_prefix = "https://github.com/" + repo_slug + "/pull/"
            pull_requests = list(map(lambda pr: int(pr[len(pull_request_url_prefix):]), pull_requests_str.split(",")))
            pr_number = max(pull_requests)
    else:
        pr_number = pr_from_fork
    return pr_number


def init_circleci_variables(ci_variables):
    ci_variables.ci = get_env("CI")
    ci_variables.ci_name = get_env("CIRCLECI")
    ci_variables.repo_slug = get_env("CIRCLE_PROJECT_USERNAME") + '/' + get_env("CIRCLE_PROJECT_REPONAME")
    ci_variables.pull_request_number = get_circleci_pr_number(ci_variables.repo_slug)
    ci_variables.build_id = get_env("CIRCLE_BUILD_NUM")


def get_jenkins_repo_slug(git_url):
    m = re.search(':([^\/]*)/([^\.]*)\.git', git_url)
    return m.group(1) + '/' + m.group(2)


def init_jenkins_variables(ci_variables):
    ci_variables.ci = "true"
    ci_variables.ci_name = "true"
    git_url = get_env("GIT_URL")
    if git_url is not None:
        ci_variables.repo_slug = get_jenkins_repo_slug(get_env("GIT_URL"))
    ci_variables.pull_request_number = get_env("gitlabMergeRequestId")
    ci_variables.build_id = get_env("BUILD_ID")
    ci_variables.job_name = get_env("JOB_NAME")


def get_gitlabci_repo_slug(build_repo):
    m = re.search('\@([^\/]*)\/([^\.]*)\.git', build_repo)
    return m.group(2)


def init_gitlabci_variables(ci_variables):
    ci_variables.ci = "true"
    ci_variables.ci_name = "true"
    ci_variables.repo_slug = get_gitlabci_repo_slug(get_env("CI_BUILD_REPO"))
    ci_variables.build_id = get_env("CI_BUILD_ID")
    ci_variables.pull_request_number = get_env("MERGE_REQUEST_ID")


def init_variables():
    ci_variables = CIVariables()
    ci_variables.ci_service_name = detect_ci_service_name()
    logging.info("Detected CI " + ci_variables.ci_service_name)
    if ci_variables.ci_service_name == 'TRAVIS':
        init_travis_variables(ci_variables)
    elif ci_variables.ci_service_name == 'CIRCLECI':
        init_circleci_variables(ci_variables)
    elif ci_variables.ci_service_name == 'JENKINS':
        init_jenkins_variables(ci_variables)
    elif ci_variables.ci_service_name == 'GITLAB_CI':
        init_gitlabci_variables(ci_variables)

    ci_variables.api_key = get_env("sputnik_api_key")
    return ci_variables


def unzip(zip):
    zip_ref = zipfile.ZipFile(zip, 'r')
    zip_ref.extractall(".")
    zip_ref.close()


def download_file(url, file_name):
    logging.info("Downloading " + file_name)
    try:
        urlretrieve(url, filename=file_name)
    except Exception:
        logging.error("Problem while downloading " + file_name + " from " + url)


def query_params(ci_variables):
    query_vars = {}
    query_vars['key'] = ci_variables.api_key
    query_vars['build_id'] = ci_variables.build_id
    return urlencode(dict((k, v) for k,v in query_vars.items() if v is not None))


def are_credentials_correct(ci_variables):
    logging.info("Checking credentials")
    check_key_request = Request(sputnik_base_url + "api/" + provider + "/" + ci_variables.repo_slug + "/credentials?" + query_params(ci_variables))
    code = None
    try:
        response = urlopen(check_key_request)
        code = response.code
    except HTTPError as e:
        code = e.code
    return code == 200


def download_files_and_run_sputnik(ci_variables):
    if ci_variables.is_pull_request_initiated():
        if not are_credentials_correct(ci_variables):
            logging.error("API key or build id is incorrect. Please make sure that you passed correct value to CI settings.")
            return

        configs_url = sputnik_base_url + "conf/" + provider + "/" + ci_variables.repo_slug + "/configs?" + query_params(ci_variables)
        download_file(configs_url, "configs.zip")
        unzip("configs.zip")

        global sputnik_version
        sputnik_jar_url = "https://repo1.maven.org/maven2/pl/touk/sputnik/" + sputnik_version + "/sputnik-" + sputnik_version + "-all.jar"
        logging.debug('Sputnik jar url: ' + sputnik_jar_url)
        download_file(sputnik_jar_url, "sputnik.jar")

        sputnik_params = ['--conf', 'sputnik.properties', '--pullRequestId', str(ci_variables.pull_request_number)]
        if ci_variables.api_key is not None:
            sputnik_params = sputnik_params + ['--apiKey', ci_variables.api_key]
        if ci_variables.build_id is not None:
            sputnik_params = sputnik_params + ['--buildId', ci_variables.build_id]
        sputnik_params = sputnik_params + ['--provider', provider]
        subprocess.call(['java', '-jar', 'sputnik.jar'] + sputnik_params)


def sputnik_ci():
    configure_logger()

    print("""
          _____             _         _ _
         / ____|           | |       (_) |
        | (___  _ __  _   _| |_ _ __  _| | __
         \___ \| '_ \| | | | __| '_ \| | |/ /
         ____) | |_) | |_| | |_| | | | |   <
        |_____/| .__/ \__,_|\__|_| |_|_|_|\_\\
               | |
               |_|
               """)
    print("Running on Python " + platform.python_version() + "\n")
    print("Using Sputnik version " + sputnik_version + "\n")

    ci_variables = init_variables()

    if ci_variables.is_set_every_required_env():
        download_files_and_run_sputnik(ci_variables)
    elif ci_variables.pull_request_number is None:
        logging.info("Pull/merge request not initiatied")
    else:
        logging.info("Env variables needed to run not set. Aborting.")


sputnik_ci()
