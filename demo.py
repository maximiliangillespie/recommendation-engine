import redis 
import json
from json.encoder import INFINITY
import math
import numpy as np
import pandas as pd
from flask import Flask
from flask import request

# CONSTANTS
focus_user = 2
focus_user_key = "user:" + str(focus_user) + ":items"
focus_user_similars_key = "user:" + str(focus_user) + ":similars"
focus_user_suggestions_key = "user:" + str(focus_user) + ":suggestions"

client = redis.Redis(host='localhost', port=6379, charset="utf-8", decode_responses=True)
app = Flask(__name__)

################### HELPER FUNCTIONS ###################

def load_score(rating, user_id, item_id):
    user_key = "user:" + str(user_id) + ":items"
    item_key = "item:" + str(item_id) + ":scores"

    client.zadd(user_key, {int(item_id): int(rating)})
    client.zadd(item_key, {int(user_id): int(rating)})

def update_focus_user(new_focus_user):
    global focus_user, focus_user_key, focus_user_similars_key, focus_user_suggestions_key
    focus_user = new_focus_user
    focus_user_key = "user:" + str(new_focus_user) + ":items"
    focus_user_similars_key = "user:" + str(new_focus_user) + ":similars"
    focus_user_suggestions_key = "user:" + str(new_focus_user) + ":suggestions"

def fetch_candidates():
    # NOTE: for now I am assuming user 1 – TODO make this extensible for any user
    focus_user_items = client.zrange(focus_user_key, 0, -1)

    # create union of all users with mutually rated items
    items = []
    for focus_item in focus_user_items:
        focus_item_key = "item:" + str(focus_item) + ":scores"
        items.append(focus_item_key)
    client.zunionstore("ztmp", items)

    print("--------------------")
    print("FOCUS USER'S ITEMS:")
    for item in items:
        print(item)

    candidate_users = client.zrange("ztmp", 0, -1)
    return candidate_users

def calculate_candidate_similarity(candidate_users):
    candidate_user_keys = []
    print("--------------------")
    print("CANDIDATE USERS:")
    for candidate_user_id in candidate_users:
        if candidate_user_id == focus_user:
            pass
        candidate_user_key = "user:" + str(candidate_user_id) + ":items"
        print(candidate_user_key)
        candidate_user_dict = {
            focus_user_key: -1,
            candidate_user_key: 1
        }
        client.zinterstore("ztmp", candidate_user_dict)
        intersecting_items = client.zrange("ztmp", 0, -1)
        # print(json.dumps(candidate_user_dict))
        for intersecting_item in intersecting_items:
            focus_score = client.zscore(focus_user_key, intersecting_item)
            candidate_score = client.zscore(candidate_user_key, intersecting_item)
            mse = np.square(np.subtract(float(focus_score), float(candidate_score))).mean()
            rms = math.sqrt(mse)
            print("=> ITEM: " + str(intersecting_item))
            print("==> ROOT MEAN SQUARE: " + str(rms) + '\n')
            # this would be where you would filter out some users based on RMS score
            client.zadd(focus_user_similars_key, {int(candidate_user_id): int(rms)})
        candidate_user_keys.append(candidate_user_key)
    print("--------------------")
    return candidate_user_keys

def calculate_candidate_items(candidate_user_keys):
    candidate_keys_dict = {focus_user_key: -1} # initialize dictionary with score of -1 for focus user
    for candidate_user_key in candidate_user_keys:
        if candidate_user_key == focus_user_key:
            pass
        else:
            candidate_keys_dict[candidate_user_key] = 1

    print("candidate keys dict:")
    print(json.dumps(candidate_keys_dict))
    print("--------------------")

    client.zunionstore("ztmp", candidate_keys_dict, "MIN")
    items_we_want = client.zrangebyscore("ztmp", 0, 100000000)

    print("CANDIDATE ITEMS: ")
    if (len(items_we_want) == 0):
        print("no items")
    else:
        for item in items_we_want:
            print(item)
    print("--------------------")
    print("--------------------")
    
    return items_we_want

def make_suggestion(candidate_items):
    for item in candidate_items:
        item_key = "item:" + str(item) + ":scores"
        # intersect item sets, take only the item scores by using WEIGHTS
        client.zinterstore('ztmp', {focus_user_similars_key: 0, item_key: 1})
        users = client.zrange('ztmp', 0, -1)
        scores = []
        for user in users:
            scores.append(client.zscore('ztmp', user))
        mean = np.mean(scores)
        # print(mean)
        client.zadd(focus_user_suggestions_key, {item_key: mean})

    suggestions_response = "SUGGESTIONS (item | rating)\n"
    suggestions = client.zrevrange(focus_user_suggestions_key, 0, -1)
    
    for item_key in suggestions:
        item_score = client.zscore(focus_user_suggestions_key, item_key)
        suggestions_response += str(item_key) + "  |  " + str(item_score) + "\n"

    return suggestions_response

def check_user_exists(focus_user):
    return client.exists(focus_user_key)

################### API ROUTES ###################

@app.route("/loadTestData", methods=["POST"])
def API_LOAD_TEST_DATA():
    data = pd.read_csv("data.csv")
    for row in data.values:
        user_id = row[0]
        item_id = row[1]
        rating = row[2]
        load_score(rating, user_id, item_id)

    return "loaded test data successfully!"

@app.route("/ratings", methods=["POST"])
def API_ADD_RATING():
    rating = request.get_json()
    load_score(rating['rating'], rating['user_id'], rating['item_id'])
    return "Successfully loaded rating!"

@app.route("/flushall", methods=["POST"])
def API_FLUSH_DB():
    client.flushall()
    return "Successfully flushed your data :("

@app.route("/suggested/<focus_user>", methods=["GET"])
def API_GET_SUGGESTED_ITEMS(focus_user):
    # STEP 1
    update_focus_user(focus_user)

    if (check_user_exists(focus_user)):
        # STEP 2
        candidate_users = fetch_candidates()
        # STEP 3
        candidate_user_keys = calculate_candidate_similarity(candidate_users)
        # STEP 4
        candidate_items = calculate_candidate_items(candidate_user_keys)
        # STEP 5
        response = make_suggestion(candidate_items)
        return response
    else:
        return "ERROR: user does not exist"

############# MAIN METHOD #############

app.run(debug = True)
