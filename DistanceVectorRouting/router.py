#!/usr/bin/python
"""""
@File:           router.py
@Description:    Distance Vector Routing Algorithm.
@Author:         Chetan Borse
@EMail:          chetanborse2106@gmail.com
@Created_on:     04/23/2017
@License         GNU General Public License
@python_version: 2.7
===============================================================================
"""

import os
import time
import logging
import socket
import struct
import select
from collections import namedtuple
from threading import Thread
from threading import Lock
from threading import Event

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler


# Set logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s DISTANCE VECTOR ROUTING [%(levelname)s] %(message)s',)
log = logging.getLogger()


# Lock for synchronized access to 'RoutingTable'
LOCK = Lock()


class FileNotExistError(Exception):
    pass


class RouterError(Exception):
    pass


class Router(object):
    """
    Router running Distance Vector Routing algorithm.
    """

    def __init__(self,
                 routerName,
                 routerIP="127.0.0.1",
                 routerPort=8080,
                 timeout=15,
                 www=os.path.join(os.getcwd(), "data", "scenario-1")):
        self.routerName = routerName
        self.routerIP = routerIP
        self.routerPort = routerPort
        self.timeout = timeout
        self.www = www

    def open(self):
        """
        Create UDP socket.
        """
        try:
            self.routerSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.routerSocket.bind((self.routerIP, self.routerPort))
            self.routerSocket.setblocking(0)
        except Exception as e:
            log.error("Could not create UDP socket!")
            log.debug(e)
            raise RouterError("Creating UDP socket %s:%d failed!"
                              % (self.routerIP, self.routerPort))

    def start(self, routerInformation):
        """
        Start running the Distance Vector Routing algorithm.
        """
        log.info("Running Distance Vector Routing at router: %s",
                 self.routerName)

        # Create UDP socket
        log.info("Creating UDP socket %s:%d", self.routerIP, self.routerPort)
        self.open()

        log.info("Loading router information from: %s", routerInformation)
        routerInformation = os.path.join(self.www, routerInformation)
        if not os.path.exists(routerInformation):
            raise FileNotExistError("File does not exist: %s!"
                                    % routerInformation.rsplit(os.sep, 1)[1])

        # Create an object of 'RoutingTable'
        routingTable = RoutingTable(self.routerName, routerInformation)

        # Create a thread named 'DistanceVectorRouting'
        # to run Distance Vector Routing algorithm
        log.info("Creating a thread to run Distance Vector Routing algorithm")
        self.protocolHandler = DistanceVectorRouting(self.routerName,
                                                     self.routerSocket,
                                                     self.routerIP,
                                                     self.routerPort,
                                                     routingTable,
                                                     self.timeout)

        # Create a thread named 'RouterLinkMonitor'
        # to monitor links with neighbour routers
        log.info("Creating a thread to monitor links with neighbour routers")
        self.routerLinkHandler = RouterLinkMonitor(self.routerName,
                                                   routerInformation,
                                                   routingTable)

        # Start thread execution
        log.info("Starting thread execution")
        self.protocolHandler.start()
        self.routerLinkHandler.start()

        # Keep running algorithm until someone terminates it
        while True:
            time.sleep(1)

    def stop(self, timeout=5):
        """ 
        Stop running the Distance Vector Routing algorithm.
        """
        log.info("Shutting down the router: %s", self.routerName)

        try:
            self.protocolHandler.terminate(timeout+self.timeout)
        except Exception as e:
            log.error("Could not terminate the thread: %s!",
                      self.protocolHandler.threadName)
            log.debug(e)
            raise RouterError("Shutting down the router '%s' failed!"
                              % self.routerName)

        try:
            self.routerLinkHandler.terminate(timeout)
        except Exception as e:
            log.error("Could not terminate the thread: %s!",
                      self.protocolHandler.threadName)
            log.debug(e)
            raise RouterError("Shutting down the router '%s' failed!"
                              % self.routerName)

        try:
            self.close()
        except Exception as e:
            log.error("Could not shut down the socket!")
            log.debug(e)
            raise RouterError("Shutting down the router '%s' failed!"
                              % self.routerName)

    def close(self):
        """
        Close UDP socket.
        """
        try:
            if self.routerSocket:
                self.routerSocket.close()
        except Exception as e:
            log.error("Could not close UDP socket!")
            log.debug(e)
            raise RouterError("Closing UDP socket %s:%d failed!"
                              % (self.routerIP, self.routerPort))


class RoutingTable(object):
    """
    Routing Table.
    """

    def __init__(self, sourceRouter, routerInformation):
        self.sourceRouter = sourceRouter
        self.routerInformation = routerInformation
        self.neighbours = {}
        self.totalNeighbours = 0
        self.routingTable = {}
        self.load_router_information()
        self._init_distance_vector()

    def load_router_information(self):
        """
        Load router information.
        """
        with open(self.routerInformation, "r") as f:
            for info in f.readlines():
                info = filter(None, info.split())

                if len(info) == 1:
                    self.totalNeighbours = int(info[0])
                elif len(info) == 4:
                    if info[0] not in self.neighbours:
                        self.neighbours[info[0]] = {}

                    self.neighbours[info[0]]['ipv4'] = info[2]
                    self.neighbours[info[0]]['port'] = int(info[3])
                    self.neighbours[info[0]]['link_cost'] = float(info[1])

    def _init_distance_vector(self):
        """
        Initialise the distance vector.
        """
        for router in [self.sourceRouter]+list(self.neighbours.keys()):
            self.routingTable[router] = {}
            self.routingTable[router][router] = {}
            self.routingTable[router][router]['distance'] = 0
            self.routingTable[router][router]['nextHopRouter'] = router

        for neighbourRouter, routerAddress in self.neighbours.items():
            sourceDV = self.routingTable[self.sourceRouter]
            neighbourDV = self.routingTable[neighbourRouter]

            sourceDV[neighbourRouter] = {}
            sourceDV[neighbourRouter]['distance'] = routerAddress['link_cost']
            sourceDV[neighbourRouter]['nextHopRouter'] = neighbourRouter

            neighbourDV[self.sourceRouter] = {}
            neighbourDV[self.sourceRouter]['distance'] = routerAddress['link_cost']
            neighbourDV[self.sourceRouter]['nextHopRouter'] = self.sourceRouter

    def isNeighbourRouter(self, routerAddress):
        """
        Check whether the packet is received from the correct neighbour router.
        """
        for k, v in self.neighbours.items():
            if v['ipv4'] == routerAddress[0] and v['port'] == routerAddress[1]:
                return True

        return False

    def update(self,
               router=None,
               distanceVector=None,
               poisonReverse=None,
               operation="insert_distance_vector"):
        """
        Thread-safe function for updating routing table.
        """
        with LOCK:
            if operation == "insert_distance_vector":
                if router is not None and distanceVector is not None:
                    self._insert(router, distanceVector)
            elif operation == "update_distance_vector":
                if (router is not None and 
                        distanceVector is not None and 
                        poisonReverse is not None):
                    self._update(router, distanceVector, poisonReverse)
            elif operation == "update_link":
                 self.load_router_information()

    def _insert(self, router, distanceVector):
        """
        Insert or update neighbour router's distance vector in routing table.
        """
        if router not in self.routingTable:
            self.routingTable[router] = {}

        dv = self.routingTable[router]

        for destinationRouter, distance, nextHopRouter in distanceVector:
            if destinationRouter not in dv:
                dv[destinationRouter] = {}

            dv[destinationRouter]['distance'] = distance
            dv[destinationRouter]['nextHopRouter'] = nextHopRouter

    def _update(self, router, distanceVector, poisonReverse):
        """
        Update source router's distance vector in routing table.
        """
        dv = self.routingTable[self.sourceRouter]

        for destinationRouter, distance, nextHopRouter in distanceVector:
            if destinationRouter == self.sourceRouter:
                continue

            if destinationRouter not in dv:
                dv[destinationRouter] = {}

            shortestDistance = float("inf")
            nextHopRouter = router

            for neighbour, linkCost in self.neighbours.items():
                if (neighbour in self.routingTable and
                        destinationRouter in self.routingTable[neighbour]):
                    if neighbour == router and poisonReverse[destinationRouter]:
                        distance = float("inf")
                    else:
                        distance = linkCost['link_cost'] + \
                            self.routingTable[neighbour][destinationRouter]['distance']

                    if distance < shortestDistance:
                        shortestDistance = distance
                        nextHopRouter = neighbour

            dv[destinationRouter]['distance'] = shortestDistance
            dv[destinationRouter]['nextHopRouter'] = nextHopRouter

    def get_distance_vector(self):
        """
        Get a source router's distance vector.
        """
        return self.routingTable[self.sourceRouter]

    def get_neighbour_routers(self):
        """
        Get a list of neighbour routers.
        """
        return self.neighbours


class DistanceVectorRouting(Thread):
    """
    Thread for running Distance Vector Routing algorithm.
    """

    PACKET = namedtuple("Packet", ["Router",
                                   "Checksum",
                                   "DistanceVector",
                                   "PoisonReverse",
                                   "Payload"])

    def __init__(self,
                 routerName,
                 routerSocket,
                 routerIP,
                 routerPort,
                 routingTable,
                 timeout=15,
                 threadName="DistanceVectorRouting",
                 bufferSize=2048):
        Thread.__init__(self)
        self._stopevent = Event()
        self.routerName = routerName
        self.routerSocket = routerSocket
        self.routerIP = routerIP
        self.routerPort = routerPort
        self.routingTable = routingTable
        self.timeout = timeout
        self.threadName = threadName
        self.bufferSize = bufferSize

    def run(self):
        """
        Start to run Distance Vector Routing algorithm.
        """
        # Keep running algorithm until someone terminates it
        sequence_no = 1
        while not self._stopevent.isSet():
            # Send source router's distance vector to its neighbour routers
            log.info("[%s] Sending distance vector to neighbour routers",
                     self.threadName)
            log.info("[%s] Sequence Number: <%d>", self.threadName, sequence_no)
            self.send_distance_vector()

            # Start monitoring responses from neighbour routers
            # for next '15' seconds (as specified by timeout)
            start_time = time.time()
            while True:
                # If timeout, stop listening on socket
                if (time.time()-start_time) > self.timeout:
                    break

                # Listen for incoming responses on socket
                # with the provided timeout
                ready = select.select([self.routerSocket], [], [], self.timeout)
                if not ready[0]:
                    break

                # Receive packet from neighbour router
                try:
                    receivedPacket, receiverAddress = \
                                    self.routerSocket.recvfrom(self.bufferSize)
                except Exception as e:
                    log.error("[%s] Could not receive UDP packet!",
                              self.threadName)
                    log.debug(e)
                    raise RouterError("Receiving UDP packet failed!")
                else:
                    log.info("[%s] Received packet from: %s:%d",
                             self.threadName, receiverAddress[0], receiverAddress[1])

                # Verify whether the packet is received
                # from correct neighbour router
                if not self.routingTable.isNeighbourRouter(receiverAddress):
                    log.warning("[%s] Discarding packet received from wrong router!",
                                self.threadName)
                    continue

                # Parse header fields and payload from the received packet
                receivedPacket = self.parse(receivedPacket)

                # Check whether the received packet is not corrupt
                if self.corrupt(receivedPacket):
                    log.warning("[%s] Discarding corrupt received packet!",
                                self.threadName)
                    continue

                # Update routing table
                log.info("[%s] Updating routing table", self.threadName)
                self.update_routing_table(receivedPacket)

            sequence_no += 1

    def send_distance_vector(self):
        """
        Send source router's distance vector to its neighbour routers.
        """
        # Get a list of neighbour routers
        neighbourRouters = self.routingTable.get_neighbour_routers()

        # Get a source router's distance vector
        distanceVector = self.routingTable.get_distance_vector()

        # Display the distance vector to be sent
        for destinationRouter, info in distanceVector.items():
            log.debug("[%s] Shortest Path %s-%s: Cost [%f], Next Hop Router [%s]",
                      self.threadName, self.routerName, destinationRouter,
                      info['distance'], info['nextHopRouter'])

        # Send the distance vector to neighbour routers
        for neighbourRouter, routerAddress in neighbourRouters.items():
            # Poison distance vector with infinity for a destination,
            # where the neighbor router is a next hop router to that destination
            poisonReverse = {}
            for destinationRouter, shortest_path in distanceVector.items():
                if (destinationRouter != self.routerName and
                        destinationRouter != neighbourRouter and
                        neighbourRouter == shortest_path['nextHopRouter']):
                    poisonReverse[destinationRouter] = 1
                else:
                    poisonReverse[destinationRouter] = 0

            # Create a namedtuple for a packet to be sent
            pkt = DistanceVectorRouting.PACKET(Router=self.routerName,
                                               Checksum=None,
                                               DistanceVector=distanceVector,
                                               PoisonReverse=poisonReverse,
                                               Payload=None)

            # Send packet
            self.rdt_send(pkt, routerAddress)

    def rdt_send(self, packet, routerAddress):
        """
        Reliable data transfer.
        """
        # Create a raw packet
        rawPacket = self.make_pkt(packet)

        # Transmit a packet using UDP protocol
        self.udt_send(rawPacket, routerAddress)

    def make_pkt(self, packet):
        """
        Create a raw packet.
        """
        payload = []
        for destinationRouter, shortest_path in packet.DistanceVector.items():
            payload.append((destinationRouter,
                            str(shortest_path['distance']),
                            shortest_path['nextHopRouter'],
                            str(packet.PoisonReverse[destinationRouter])))
        payload = map(lambda x: ':'.join(x), payload)
        payload = ','.join(payload)

        router = struct.pack('=1s', packet.Router)
        payloadSize = struct.pack('=I', len(payload))
        checksum = struct.pack('=H', self.checksum(payload))
        payload = struct.pack('='+str(len(payload))+'s', payload)

        rawPacket = router + payloadSize + checksum + payload

        return rawPacket

    def udt_send(self, packet, routerAddress):
        """
        Unreliable data transfer using UDP protocol.
        """
        try:
            self.routerSocket.sendto(packet,
                                     (routerAddress['ipv4'], routerAddress['port']))
        except Exception as e:
            log.error("[%s] Could not send UDP packet!", self.threadName)
            log.debug(e)
            raise RouterError("Sending UDP packet to %s:%d failed!"
                              % (routerAddress['ipv4'], routerAddress['port']))

    def parse(self, receivedPacket):
        """
        Parse header fields and payload from the received packet.
        """
        router = struct.unpack('=1s', receivedPacket[0:1])[0]
        payloadSize = struct.unpack('=I', receivedPacket[1:5])[0]
        checksum = struct.unpack('=H', receivedPacket[5:7])[0]
        payload = struct.unpack('='+str(payloadSize)+'s', receivedPacket[7:])[0]

        content = filter(None, payload.split(','))
        content = map(lambda x: x.strip(), content)
        content = map(lambda x: x.split(':'), content)
        content = [d for d in content if len(d) == 4]
        distanceVector = map(lambda x: (x[0], float(x[1]), x[2]), content)
        poisonReverse = dict(map(lambda x: (x[0], int(x[3])), content))

        pkt = DistanceVectorRouting.PACKET(Router=router,
                                           Checksum=checksum,
                                           DistanceVector=distanceVector,
                                           PoisonReverse=poisonReverse,
                                           Payload=payload)

        return pkt

    def corrupt(self, receivedPacket):
        """
        Check whether the received packet is corrupt or not.
        """
        # Compute checksum for the received packet
        computedChecksum = self.checksum(receivedPacket.Payload)

        # Compare computed checksum with the checksum of received packet
        if computedChecksum != receivedPacket.Checksum:
            return True
        else:
            return False

    def checksum(self, data):
        """
        Compute and return a checksum of the given payload data
        """
        # Force payload data into 16 bit chunks
        if (len(data) % 2) != 0:
            data += "0"

        sum = 0
        for i in range(0, len(data), 2):
            data16 = ord(data[i]) + (ord(data[i+1]) << 8)
            sum = self.carry_around_add(sum, data16)

        return ~sum & 0xffff

    def carry_around_add(self, sum, data16):
        """
        Helper function for carry around add.
        """
        sum = sum + data16
        return (sum & 0xffff) + (sum >> 16)

    def update_routing_table(self, receivedPacket):
        """
        Update routing table.
        """
        router = receivedPacket.Router
        distanceVector = receivedPacket.DistanceVector
        poisonReverse = receivedPacket.PoisonReverse

        # Insert or update neighbour router's distance vector in routing table
        self.routingTable.update(router,
                                 distanceVector,
                                 operation="insert_distance_vector")

        # Update source router's distance vector in routing table
        self.routingTable.update(router,
                                 distanceVector,
                                 poisonReverse,
                                 operation="update_distance_vector")

    def terminate(self, timeout=5):
        """
        Terminate the thread.
        """
        self._stopevent.set()
        Thread.join(self, timeout)


class RouterLinkEventHandler(PatternMatchingEventHandler):
    """
    Event handler for handling events related with router links.
    """

    def on_moved(self, event):
        pass

    def on_created(self, event):
        pass

    def on_deleted(self, event):
        pass

    def on_modified(self, event):
        log.info("[%s] Router information is updated", self.threadName)
        super(RouterLinkEventHandler, self).on_modified(event)
        self.update_link()

    def update_link(self):
        # Reload router information
        self.routingTable.load_router_information()


class RouterLinkMonitor(Thread):
    """
    Thread for monitoring links with neighbour routers.
    """

    def __init__(self,
                 routerName,
                 routerInformation,
                 routingTable,
                 threadName="RouterLinkMonitor"):
        Thread.__init__(self)
        self._stopevent = Event()
        self.routerName = routerName
        self.routerInformation = routerInformation
        self.routerInformationPath = os.path.split(routerInformation)[0]
        self.routingTable = routingTable
        self.threadName = threadName

    def run(self):
        """
        Start monitoring links with neighbour routers.
        """
        log.info("[%s] Started monitoring links for a router: %s",
                 self.threadName, self.routerName)

        # Create event handler
        eventHandler = RouterLinkEventHandler(patterns=[self.routerInformation],
                                              ignore_patterns=[],
                                              ignore_directories=True)
        eventHandler.routingTable = self.routingTable
        eventHandler.threadName = self.threadName

        # Create watchdog observer
        self.observer = Observer()
        self.observer.schedule(eventHandler,
                               self.routerInformationPath,
                               recursive=False)
        self.observer.start()

        # Keep monitoring links with neighbour routers,
        # until someone terminates the thread
        while not self._stopevent.isSet():
            time.sleep(1)
        else:
            self._stop()

    def _stop(self):
        """
        Stop the watchdog observer.
        """
        self.observer.stop()
        self.observer.join()

    def terminate(self, timeout=5):
        """
        Stop the thread.
        """
        self._stopevent.set()
        Thread.join(self, timeout)
