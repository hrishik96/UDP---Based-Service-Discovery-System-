# Test cases

| # | Scenario | Action | Expected result |
|---|---|---|---|
| 1 | Self-registration | Start the registry, then a server with server_v2.py | Registry prints EVENT REGISTERED within 3 seconds |
| 2 | Service found | client_v2.py 10.0.0.1 video | SERVICE reply, latency in ms, then SUCCESS |
| 3 | Service not found | client_v2.py 10.0.0.1 audio | NOT_FOUND, then Service was not found |
| 4 | Server failure (timeout) | Stop the primary, run the client at once | Client times out on the primary, rediscovers, gets SUCCESS from the backup |
| 5 | Unavailable server detected | Wait 9 seconds after stopping the primary | Registry prints EVENT EXPIRED |
| 6 | SDN reaction | Same moment as test 5 | POX logs SDN REACTION and the switch shows a priority 300 DROP rule for the dead server |
| 7 | Traffic blocked | probe.py 10.0.0.2 5001 50 | tx pkts on the dead server port rises by about 1 (52 under the static controller) |
| 8 | Recovery | Restart the primary | Registry prints EVENT REGISTERED, POX removes the DROP rule |
| 9 | Load | measure.py with 1, 5, 10 and 20 clients | 0 lost requests, mean latency about 1 ms |
| 10 | Invalid request | Send a malformed message to the registry | INVALID_REQUEST (passed, checked on the VM with nc) |
