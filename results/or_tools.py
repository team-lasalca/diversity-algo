#!/usr/bin/env python
# coding: utf-8

# In[16]:

import sys
import pandas as pd
import numpy as np
from json import loads, dumps
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from scipy.spatial import distance_matrix
import subprocess


# In[17]:


inf = int(1e10)
max_time = (24 - 6) * 60
start = 6 * 60


# In[18]:

#DATA_IN_PATH = "../phystech-master/kamil/cls_input.json"
#DATA_OUT_PATH = "../phystech-master/kamil/cls_output.json"
DATA_IN_PATH = sys.argv[1]
DATA_OUT_PATH = sys.argv[2]


# In[19]:


with open(DATA_IN_PATH, 'r') as file:
    data_in_json = file.read()


# In[20]:


data_in_python = loads(data_in_json)
columns = list(data_in_python.keys())
columns


# In[21]:


dfs = {}
for key, value in data_in_python.items():
    dfs[key] = pd.DataFrame(value)

couriers = dfs["couriers"]
depots = dfs["depots"]
orders = dfs["orders"]


# In[22]:


places = []
places_simple = []
pickups_deliveries = []
time_windows = []

'''
for _, depot in depots.iterrows():
    place = {"point_id": depot["point_id"], "x": depot["location_x"], "y": depot["location_y"], "type": "depot"}
    places_simple.append([place["x"], place["y"]])
    time_windows.append([0, max_time])
    places.append(place)
'''

for i, order in orders.iterrows():    
    place = {"point_id": order["pickup_point_id"], "x": order["pickup_location_x"], "y": order["pickup_location_y"], "from": order["pickup_from"], "to": order["pickup_to"], "type": "pickup"}
    place2 = {"point_id": order["dropoff_point_id"], "x": order["dropoff_location_x"], "y": order["dropoff_location_y"], "from": order["dropoff_from"], "to": order["dropoff_to"], "type": "dropoff"}
    if place["from"] >= place["to"] or place2["from"] >= place2["to"]:
        orders.drop(i)
        continue
    
    pickups_deliveries.append([len(places_simple), len(places_simple) + 1])
    
    places_simple.append([place["x"], place["y"]])
    time_windows.append([place["from"] - start, place["to"] - start])
    places.append(place)
    
    places_simple.append([place2["x"], place2["y"]])
    time_windows.append([place2["from"] - start, place2["to"] - start])
    places.append(place2)

route_start = len(places_simple)
for _, courier in couriers.iterrows():
    places_simple.append([courier["location_x"], courier["location_y"]])
    time_windows.append([0, max_time])

places = pd.DataFrame(places)
distances = distance_matrix(x=places_simple, y=places_simple, p=1) + 10
distances = np.append(distances, np.zeros(distances.shape[0]).reshape(-1, 1), axis=1)
distances = np.append(distances, np.zeros(distances.shape[1]).reshape(1, -1), axis=0)
time_windows.append([0, max_time])


# In[23]:


orders.drop("pickup_location_x", axis=1, inplace=True)
orders.drop("pickup_location_y", axis=1, inplace=True)
orders.drop("pickup_from", axis=1, inplace=True)
orders.drop("pickup_to", axis=1, inplace=True)

orders.drop("dropoff_location_x", axis=1, inplace=True)
orders.drop("dropoff_location_y", axis=1, inplace=True)
orders.drop("dropoff_from", axis=1, inplace=True)
orders.drop("dropoff_to", axis=1, inplace=True)


# In[25]:


print("couriers:", couriers.shape)
print("places:", places.shape)
print("orders:", orders.shape)


# In[26]:


def print_solution(data, manager, routing, solution):
    """Prints solution on console."""
    max_route_distance = 0
    json = []
    
    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        plan_output = 'Route for vehicle {}:\n'.format(vehicle_id)
        route_distance = 0
        
        plan_output += 'START ->';
        while not routing.IsEnd(index):
            if manager.IndexToNode(index) < places.index.stop:
                place = places.iloc[manager.IndexToNode(index)]
                plan_output += ' {} -> '.format(place["point_id"])
                
                order_id = orders[((orders["pickup_point_id"] == place["point_id"]) | (orders["dropoff_point_id"] == place["point_id"]))]["order_id"]
                if len(order_id) != 0:
                    order_id = order_id.head(1)
                else:
                    order_id = -1
                
                current_json = {
                    "courier_id": int(couriers.iloc[vehicle_id]["courier_id"]),
                    "action": place["type"], # check depot
                    "order_id": int(order_id),
                    "point_id": int(place["point_id"]),
                }
                json.append(current_json)
                
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id)
        
        if manager.IndexToNode(index) < places.index.stop:
            plan_output += '{}\n'.format(manager.IndexToNode(index))
        else:
            plan_output += 'END\n'
        plan_output += 'Distance of the route: {}m\n'.format(route_distance)
        print(plan_output)
        max_route_distance = max(route_distance, max_route_distance)
    print('Maximum of the route distances: {}m'.format(max_route_distance))
    return json


# In[27]:


data = {}
data["time_matrix"] = distances
data["time_windows"] = time_windows
data["num_vehicles"] = len(couriers)
data["starts"] = list(range(route_start, len(distances) - 1))
data["ends"] = [len(distances) - 1] * len(couriers)
data["pickups_deliveries"] = pickups_deliveries


# In[28]:



manager = pywrapcp.RoutingIndexManager(len(data["time_matrix"]), data["num_vehicles"], data["starts"], data["ends"])
routing = pywrapcp.RoutingModel(manager)

def time_callback(from_index, to_index):
    from_node = manager.IndexToNode(from_index)
    to_node = manager.IndexToNode(to_index)
    return data["time_matrix"][from_node][to_node]

transit_callback_index = routing.RegisterTransitCallback(time_callback)
routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

dimension_name = 'Time'
routing.AddDimension(
    transit_callback_index,
    max_time,  # inf slack
    max_time,  # vehicle maximum travel distance
    False,  # start cumul to zero
    dimension_name)

time_dimension = routing.GetDimensionOrDie(dimension_name)

for location_idx in range(route_start):    
    time_window = data["time_windows"][location_idx]
    index = manager.NodeToIndex(location_idx)
    time_dimension.CumulVar(index).SetRange(int(time_window[0]), int(time_window[1]))

for vehicle_id in range(data['num_vehicles']):
    index = routing.Start(vehicle_id)
    time_dimension.CumulVar(index).SetRange(int(data['time_windows'][-1][0]),
                                            int(data['time_windows'][-1][1]))

for i in range(data['num_vehicles']):
    routing.AddVariableMinimizedByFinalizer(
        time_dimension.CumulVar(routing.Start(i)))
    routing.AddVariableMinimizedByFinalizer(
        time_dimension.CumulVar(routing.End(i)))

for i, place in places.iterrows():
    order_payment = orders[((orders["pickup_point_id"] == place["point_id"]) | (orders["dropoff_point_id"] == place["point_id"]))]["payment"]
    if len(order_payment) != 0:
        order_payment = order_payment.head(1)
    else:
        order_payment = 0
    routing.AddDisjunction([manager.NodeToIndex(i)], int(order_payment))

for request in data["pickups_deliveries"]:
    pickup_index = manager.NodeToIndex(request[0])
    delivery_index = manager.NodeToIndex(request[1])
    routing.AddPickupAndDelivery(pickup_index, delivery_index)
    routing.solver().Add(
        routing.VehicleVar(pickup_index) == routing.VehicleVar(
            delivery_index))
    routing.solver().Add(
        time_dimension.CumulVar(pickup_index) <=
        time_dimension.CumulVar(delivery_index))

search_parameters = pywrapcp.DefaultRoutingSearchParameters()
search_parameters.time_limit.seconds = 60 * 60
search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

solution = routing.SolveWithParameters(search_parameters)


# In[29]:


if solution:
    print(routing.status())
    
    json = print_solution(data, manager, routing, solution)
    with open(DATA_OUT_PATH, "w") as out:
        out.write(dumps(json))
    print("Done.")


# In[30]:


try:
    out = subprocess.check_output(["python3", "check.py", DATA_IN_PATH, DATA_OUT_PATH]).decode("ascii")
    out_profit = int(out[out.find("Profit: ") + 8:])
    
    print("Profit:", out_profit)

    if out_profit < 0:
        with open(DATA_OUT_PATH, "w") as out:
            out.write(dumps([]))
        print("Rewritten.")
except Exception as ex:
    print("Test failed:\n", ex)