import argparse
import json
import multiprocessing
import os
import signal
import time
from urlparse import urlparse

import uncurl_lib
import pjfapi


def dump_json_header_to_string(header_data):
    decode_json = json.loads(header_data)
    header_all = ""
    for key in decode_json:
        header = key + ": " + decode_json[key] + "\r\n"
        header_all += header

    return header_all


def uncurl_url_link(url_link):
    result_string, result_dict = uncurl_lib.parse(url_link)

    uncurl_url = urlparse(result_dict["url"])
    uncurl_method = str(result_dict["method"]).upper()
    uncurl_data = result_dict["data_token"]
    uncurl_header_json = result_dict["headers_token"]

    header = dump_json_header_to_string(uncurl_header_json)

    data_str = '{method} {path}  HTTP/1.1\r\nHost: {host}\r\n' \
               '{header}\r\n\r\n***{inject_data}***'. \
        format(method=uncurl_method,
               path=uncurl_url.path,
               host=uncurl_url.hostname,
               header=header,
               inject_data=uncurl_data)

    return uncurl_url.hostname, uncurl_url.port, data_str


def get_statistics(conf_data, host, port, secure):
    parsed = pjfapi.HTTPRequestParser(
        pjfapi.clean_template(conf_data, pjfapi.check_template(conf_data)[0]))
    #  perform 10 requests and calculate average statistics
    statistics = pjfapi.calculate_average_statistics(host, port,
                                                     parsed, secure)
    return statistics


def hzx_main(url_link):
    """
    Main routine do the hard job
    """

    #  init the printer thread
    pjfapi.init_printer()
    pjfapi.print_queue.put("Starting iFuzz...")

    # create a Queue used to communicate results
    # between created processes and main process
    process_queue = multiprocessing.Queue(0)

    #  let's notify the user that we are starting the real fuzzing now!
    pjfapi.print_queue.put("Start fuzzing in a few seconds...")

    # get metadata
    host, port, conf_data = uncurl_url_link(url_link)
    process_number = 5
    threads_per_process = 10
    is_strong_fuzz = True
    secure = False

    #  calculate initial request statistics
    try:
        #  parse the request without injection marker
        statistics = get_statistics(conf_data, host, port, secure)
        #  if we don't have stats, quit (check hashes)!
        if None in statistics[3]:
            pjfapi.print_queue.put("Unable to retrieve stats :(")
            return pjfapi.bye()
    # ooops something wrong happened let's notify the user
    except Exception as e:
        pjfapi.print_queue.put(e)
        return pjfapi.bye()

    # start processes and return a process pool
    process_pool = pjfapi.start_processes(host, port, conf_data,
                                          secure, process_queue, statistics,
                                          process_number, threads_per_process,
                                          is_strong_fuzz)

    while True:
        try:
            while not process_queue.empty():
                #  if queue is not empty we have some results from a process
                # let's print it by adding it to print_queue
                pjfapi.print_queue.put(process_queue.get())
                #  sleep to prevent high CPU usage
                time.sleep(0.1)
        except KeyboardInterrupt:
            #  we got ctrl+c so let's kill al processes
            pjfapi.print_queue.put("Killing all processes, please wait...")
            for process in process_pool:
                #  Send sigkill to each process
                os.kill(process.pid, signal.SIGKILL)
            # exit the loop
            break
    return pjfapi.bye()


def hzx_argu_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs='+',
                        help="input url")

    args = parser.parse_args()

    return args

if __name__ == "__main__":
    url = """
         curl  http://10.187.2.200:9797/v2.0/vips/33d85b32-c3f8-4488-b8ac-8aebea032430/backends.json
         -X POST -H "X-Auth-Token: b070b1318a0d4679a2511aff3a04a3f8"
         -H "Content-Type: application/json" -H "Accept: application/json"
          -H "User-Agent: python-protonclient"
          -d '{"backend": {"port_id": "95a95519-ea84-4538-a8c3-d1ef4ad42d0c", "vip_id": "33d85b32-c3f8-4488-b8ac-8aebea032430", "weight": "200"}}'
        """
    # uncurl_url_link(url)
    hzx_main(url)