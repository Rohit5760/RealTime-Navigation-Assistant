#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from ultralytics import YOLO
import numpy as np
import queue

model=YOLO("yolo26n.pt")

tts_queue = queue.Queue()


# In[ ]:


direction_label = {
    "center":       "ahead",
    "left":         "on your left",
    "right":        "on your right",
    "extreme left":  "far to your left",
    "extreme right": "far to your right",
}


# In[ ]:


class_profile = {
#   class_name    : (danger_weight, min_proximity_to_announce)
    "car"         : (1.3,  0.15),
    "truck"       : (1.3,  0.15),
    "bus"         : (1.3,  0.15),
    "train"       : (1.4,  0.10),
    "motorcycle"  : (1.2,  0.20),
    "bicycle"     : (1.1,  0.25),
    "bear"        : (1.3,  0.20),
    "elephant"    : (1.3,  0.20),
    "horse"       : (1.1,  0.25),
    "person"      : (1.0,  0.25),
    "dog"         : (0.9,  0.30),
    "cow"         : (1.0,  0.25),
    "sheep"       : (0.85, 0.35),
    "skateboard"  : (1.0,  0.30),
    "suitcase"    : (0.9,  0.35),
    "chair"       : (0.8,  0.40),
    "dining table": (0.8,  0.40),
    "couch"       : (0.75, 0.45),
    "bed"         : (0.75, 0.45),
    "refrigerator": (0.75, 0.45),
    "potted plant": (0.7,  0.50),
    "bench"       : (0.7,  0.50),
    "cat"         : (0.65, 0.55),
    "fire hydrant": (0.8,  0.40),
    "stop sign"   : (0.5,  0.55),
    "traffic light": (0.5, 0.55),
    "parking meter": (0.5, 0.55),
    "umbrella"    : (0.6,  0.55),
}


# In[ ]:


allowed_classes = [
    # People
    0,   # person

    # Vehicles — outdoor
    1,   # bicycle
    2,   # car
    3,   # motorcycle
    5,   # bus
    6,   # train
    7,   # truck

    # Traffic infrastructure
    9,   # traffic light
    10,  # fire hydrant
    11,  # stop sign
    12,  # parking meter

    # Static outdoor obstacles
    13,  # bench

    # Animals — realistically encountered
    15,  # cat
    16,  # dog
    17,  # horse
    18,  # sheep
    19,  # cow
    20,  # elephant
    21,  # bear

    # Ground-level moving hazards
    36,  # skateboard

    # Carried/dropped obstacles
    25,  # umbrella  ← borderline, your call
    28,  # suitcase

    # Indoor furniture
    56,  # chair
    57,  # couch
    58,  # potted plant
    59,  # bed
    60,  # dining table
    72,  # refrigerator
]


# In[ ]:


state_label = {
    "stationary": "",
    "new": "",
    "approaching": "getting closer",
    "receding": "gettig farther"
}

