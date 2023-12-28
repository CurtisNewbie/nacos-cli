import sys, os
import argparse
import time, datetime
import threading
import json
import requests

LIST_INSTANCES_CMD = "list-instances"

class BaseCommand():
    def __init__(self, host, access_token, namespace):
        self.host = host
        self.access_token = access_token
        self.namespace = namespace

def login(session: requests.Session, host: str, username: str, password: str):
    res = session.post(f"{host}/nacos/v1/auth/login", data={"username" : username, "password": password })
    if res.status_code != 200:
        print(res.text)
        return None
    return json.loads(res.text)


def list_intances(session: requests.Session, host: str, access_token: str, service_name: str, namespace: str,
                   group="DEFAULT_GROUP", cluster="DEFAULT", limit=200, page=1):
    res = session.get(
        url=f'{host}/nacos/v1/ns/catalog/instances?accessToken={access_token}&serviceName={service_name}&clusterName={cluster}&groupName={group}&pageSize={limit}&pageNo={page}&namespaceId={namespace}',
        timeout=1000).text
    if res.startswith("caused"): return None
    return json.loads(res)


def log_instances(session: requests.Session, host: str, access_token: str, service_name: str, namespace: str, lock: threading.Lock,
                  unhealthy_services: list[str]):
    res = list_intances(session, host, access_token, service_name, namespace)
    if not res:
        log = f"{str(datetime.datetime.now())} {service_name:<20} has total {0:<2} instances"
        # print(log)
        with lock: unhealthy_services.append(log)
        return

    listed = res['list']
    healthy = []
    unhealthy = []
    enabled = []
    disabled = []
    count = res['count']
    ips = []
    weights = {}
    for l in listed:
        if not l['healthy']: unhealthy.append(l)
        else: healthy.append(l)

        if not l['enabled']: disabled.append(l)
        else: enabled.append(l)
        ips.append(l['ip'])

        weight = l['weight']
        if weight in weights: weights[weight].append(l['ip'])
        else: weights[weight] = [l['ip']]

    weights_str = "{ "
    sorted_weights_keys = sorted(weights.keys())
    for i in range(len(sorted_weights_keys)):
        weights_str += str(sorted_weights_keys[i]) + ": " + str(weights[sorted_weights_keys[i]])
        if i < len(sorted_weights_keys) - 1: weights_str += ", "
    weights_str += " }"

    log = f'{str(datetime.datetime.now())} {service_name:<20} has total {count:<2} instances, {len(healthy)} healthy, {len(unhealthy)} unhealthy, {len(enabled)} enabled, {len(disabled)} disabled, weights: {weights_str}'
    weight_above_zero = True
    for k in weights:
        if float(k) <= 0.0: weight_above_zero = False

    if not weight_above_zero or len(listed) < 1 or len(unhealthy) > 0 or len(disabled) > 0:
        with lock: unhealthy_services.append(log)
    else:
        print(log)

if __name__ == '__main__':

    ap = argparse.ArgumentParser(description="Nacos Cli by Yongjie.Zhuang", formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument('--host', type=str, help='host', required=True)
    ap.add_argument('--username', type=str, help='username', required=True)
    ap.add_argument('--password', type=str, help='password', required=True)
    ap.add_argument('--namespace', type=str, help='namespace', required=True)
    ap.add_argument('--command', type=str, help='command: [ \'list-instances\' ]', required=True)
    ap.add_argument('--services', type=str, help='service names delimited by comma')
    ap.add_argument('--watch', action="store_true", help='enable watch mode')
    args = ap.parse_args()

    session = requests.Session()
    login_res = login(session, args.host, args.username, args.password)
    if not login_res:
        print("Login failed")
        exit(1)

    print(f"Logged in on '{args.host}' as '{args.username}'")
    print(f"Using namespace: '{args.namespace}'")
    print()

    cred = BaseCommand(host=args.host, access_token=login_res['accessToken'], namespace=args.namespace)

    # we only support list-instances command so far
    if args.command == LIST_INSTANCES_CMD:
        if not args.services: exit(0)
        watch = args.watch
        services = args.services.split(",")

        while True:
            lock = threading.Lock()
            unhealthy_services = []
            threads = []

            for service_name in services:
                task = threading.Thread(target=log_instances,
                                         args=(session, cred.host, cred.access_token, service_name, cred.namespace,
                                               lock, unhealthy_services))
                threads.append(task)
            for t in threads: t.start()
            for t in threads: t.join()
            if len(unhealthy_services) > 0:
                print(f"\nFound {len(unhealthy_services)} services with unhealthy instances")
                for log in unhealthy_services: print(log)
            print()

            threads = []
            unhealthy_services = []

            if not watch: break
            time.sleep(1)

