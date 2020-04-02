"""
Simple storage node for a distributed file system.
"""

import configparser
import hashlib
import logging
import os
import socketserver
import sys
import tqdm
import utilities


BUFFER_SIZE = 1024
LOG_DIR = 'logs'
SCRIPT_NAME = os.path.basename(__file__)
SEPARATOR = "<>"

GET_REQUEST = "<GET_REQUEST>"
PUT_REQUEST = "<PUT_REQUEST>"
STATUS_REQUEST = "<STATUS_REQUEST>"
SERVER_AVAILABLE_CODE = "200"
TRANSFER_SUCCESSFUL_CODE = "TRANSFER_SUCCESSFUL"

logger = logging.getLogger(SCRIPT_NAME)


class DistributedNodeHandler(socketserver.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def setup(self):
        self.HOST, self.PORT = self.server.server_address
        self.STORAGE_DIR = f'storage_{self.HOST}_{self.PORT}'
        self.LOG_FILE = f'node_{self.HOST}_{self.PORT}.log'

    def handle(self):
        response_message = "Operation failed."
        # self.request is the TCP socket connected to the client
        received = self.request.recv(BUFFER_SIZE).decode()
        info_list = received.split(SEPARATOR)
        request_type = info_list[0]

        if request_type == GET_REQUEST:
            logger.debug("Received get request")
            response_message = self.do_get_handler(info_list[1:])
        elif request_type == PUT_REQUEST:
            logger.debug("Received put request")
            response_message = self.do_put_handler(info_list[1:])
        elif request_type == STATUS_REQUEST:
            logger.debug("Received status request")
            response_message = SERVER_AVAILABLE_CODE
        else:
            response_message = "Request type not supported yet!"

        # send client response
        self.request.sendall(bytes(response_message, "utf-8"))


    def do_put_handler(self, recvd_info_list):
        filename, file_size, file_hash = recvd_info_list
        # remove absolute path if there is
        filename = os.path.basename(filename)
        # convert to integer
        file_size = int(file_size)

        try:
            # start receiving the file from the socket
            # and writing to the file stream
            progress = tqdm.tqdm(
                range(file_size),
                f"Receiving {filename}", unit="B",
                unit_scale=True, unit_divisor=1024
            )

            if not os.path.exists(self.STORAGE_DIR):
                os.makedirs(self.STORAGE_DIR)
            storage_filepath = f"{self.STORAGE_DIR}/{filename}"

            total_bytes_read = 0

            with open(storage_filepath, "wb") as f:
                for _ in progress:
                    # read 1024 bytes from the socket (receive)
                    bytes_read = self.request.recv(BUFFER_SIZE)
                    if not bytes_read:
                        # nothing is received
                        # file transmitting is done
                        break
                    total_bytes_read += len(bytes_read)
                    # write to the file the bytes we just received
                    f.write(bytes_read)
                    # update the progress bar
                    progress.update(len(bytes_read))
                    # done reading the entire file
                    if total_bytes_read == file_size:
                        break

            is_file_valid = utilities.is_file_integrity_matched(
                filepath=storage_filepath,
                recvd_hash=file_hash
            )
            if is_file_valid:
                logger.debug(f"{storage_filepath} saved successfully. Integrity check passed.")
                response_message = TRANSFER_SUCCESSFUL_CODE
        except Exception as e:
            logger.error(str(e))
            response_message = str(e)
        return response_message

    def do_get_handler(self, recvd_info_list):
        pass


def main():
    HOST, PORT = utilities.get_sn_host_port(sn_num=int(sys.argv[1]))
    LOG_FILE = f'node_{HOST}_{PORT}.log'
    utilities.setup_logging(log_dir=LOG_DIR, log_file=LOG_FILE)

    server = None
    try:
        # Create the server, binding to HOST on PORT
        with socketserver.ForkingTCPServer(
                (HOST, PORT), DistributedNodeHandler) as server:
            # Activate the server; this will keep running until you
            # interrupt the program with Ctrl-C
            logger.info(f"Starting server on {HOST}:{PORT}")
            server.serve_forever()
    except Exception as e:
        logger.exception(str(e))
        if server:
            server.shutdown()


if __name__ == "__main__":
    main()
