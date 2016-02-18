#!/usr/bin/python

import logging, os, subprocess, sys, urllib

def configure_logger():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)


def get_env(single_env):
    try:
        assert (os.environ[single_env])
        return os.environ[single_env]
    except Exception:
        logging.warn("Problem while reading env variable: " + single_env)
        return None


def is_set_every_required_env_variable():
    logging.info("Check required env variables")
    required_vars = ["CI", "TRAVIS", "TRAVIS_PULL_REQUEST", "TRAVIS_REPO_SLUG"]
    for env_var in required_vars:
        if get_env(env_var) is None:
            logging.error("Env variable " + env_var + " is required to run sputnik")
            return False
    return True


def is_travis_ci():
    if get_env("CI") == 'true' and get_env("TRAVIS") == 'true' and get_env("TRAVIS_PULL_REQUEST") != "false":
        return True
    else:
        logging.warn("Stop travis continuous integration. Check evn variables CI: " + get_env("CI")
                     + ", TRAVIS: " +  get_env("TRAVIS") + ", TRAVIS_PULL_REQUEST: " + get_env("TRAVIS_PULL_REQUEST"))
        return False


def download_file(url, file_name):
    logging.info("Downloading " + file_name)
    try:
        urllib.urlretrieve(url, filename=file_name)
    except Exception:
        logging.error("Problem while downloading " + file_name + " from " + url)


def download_files_and_run_sputnik():
    if is_travis_ci():
        if get_env("api_key"):
            properties_url = "http://sputnik.touk.pl/conf/" + get_env("TRAVIS_REPO_SLUG") + "/sputnik-properties?key=" + get_env("api_key")
            download_file(properties_url, "sputnik.properties")

            checkstyle_url = "http://sputnik.touk.pl/conf/" + get_env("TRAVIS_REPO_SLUG") + "/checkstyle?key=" + get_env("api_key")
            download_file(checkstyle_url, "checkstyle.xml")

        sputnik_jar_url = "https://philanthropist.touk.pl/nexus/service/local/artifact/maven/redirect?r=snapshots&g=pl.touk&a=sputnik&c=all&v=LATEST"
        download_file(sputnik_jar_url, "sputnik.jar")

        subprocess.call(['java', '-jar', 'sputnik.jar', '--conf', 'sputnik.properties', '--pullRequestId', get_env("TRAVIS_PULL_REQUEST")])


def sputnik_ci():
    configure_logger()
    if is_set_every_required_env_variable():
        download_files_and_run_sputnik()


sputnik_ci()
