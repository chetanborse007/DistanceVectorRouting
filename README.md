# DISTANCE VECTOR ROUTING ALGORITHM


## DESCRIPTION
This is an implementation of Distance Vector Routing algorithm. The objective of this project is to implement 
an application that can be run either at several different machines or in a single machine. Implementation also 
handles link cost changes.

Instead of implementing the exact distance vector routing protocol described in the textbook, we have developed 
a variation of the protocol. In this protocol, each host sends out the routing information to its neighbours at 
a certain frequency (once every 15 seconds), regardless whether the information has changed since the last announcement. 
This strategy improves the robustness of the protocol. For instance, a lost message will be automatically recovered 
by later messages. In this strategy, typically a host re-computes its distance vector and routing table right before 
sending out the routing information to its neighbours.


## DISTANCE VECTOR ROUTING
Distance-vector routing protocols use the Bellman–Ford algorithm, Ford–Fulkerson algorithm, or DUAL FSM to calculate paths.

Routers using distance-vector protocol do not have knowledge of the entire path to a destination. Instead they use two methods:
1.	Direction in which router or exit interface a packet should be forwarded.
2.	Distance from its destination

Distance-vector protocols are based on calculating the direction and distance to any link in a network. "Direction" usually 
means the next hop address and the exit interface. "Distance" is a measure of the cost to reach a certain node. The least cost 
route between any two nodes is the route with minimum distance. Each node maintains a vector (table) of minimum distance to 
every node. The cost of reaching a destination is calculated using various route metrics. 

Updates are performed periodically in a distance-vector protocol where all or part of a router's routing table is sent to all 
its neighbours that are configured to use the same distance-vector routing protocol. Once a router has this information it can 
amend its own routing table to reflect the changes and then inform its neighbours of the changes. This process has been described 
as ‘routing by rumour’ because routers are relying on the information they receive from other routers and cannot determine if the 
information is valid and true.

Rerefence: https://en.wikipedia.org/wiki/Distance-vector_routing_protocol


## POISON REVERSE
Algorithm uses Poison Reverse as a solution to count to infinity problem.

If Z routes through Y to get to X , then Z tells Y its (Z’s) distance to X is infinite (so Y won’t route to X via Z).


## INPUT FORMAT
Routing information file should have format as below,
	<Total Neighbor Routers>
	<Router Name> <Link Cost> <IP Address> <Port>
	.
	.
	<Router Name> <Link Cost> <IP Address> <Port>


## HOW TO RUN
If there are 'n' routers, then run ClientApp.py in 'n' different terminals.
	python ClientApp.py -n [router_name] -i [router_ip] -p [router_port] -f [router_information] -t [timeout] -w [www]
	e.g. python ClientApp.py -n a -i 127.0.0.1 -p 8080 -f a.dat -t 15


## CHANGE IN LINK COST
One can directly change link costs in routing information file to simulate link cost change scenario.
Implementation automatically handles such link cost changes and update distance vectors at every router.


## MAINTAINER
 - Name:        Chetan Borse
 - EMail ID:    chetanborse2106@gmail.com
 - LinkedIn:    https://www.linkedin.com/in/chetanrborse
