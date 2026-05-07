#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import numpy as np
from collections import deque
from object_detection_models import model, tts_queue, direction_label, class_profile, allowed_classes, state_label
import threading
import win32com.client
import pythoncom

# In[ ]:


approaching_threshold = 0.02
receding_threshold = 0.02
stale_after = 10
history_len = 6

frame_counter = 0
tracking_hist = {}
announced = {}


# In[ ]:



# In[ ]:


def bottom_bias(y_bottom):
  if y_bottom <= 0.5:
    return 1

  bias = 1 + (y_bottom - 0.5)

  return bias


# In[ ]:


def direction_score(x_center):
  std = 0.3
  low = 0.4 
  high = 1

  x = ((x_center - 0.5)**2) / (2 * std**2)
  raw = np.exp(-x)

  return low + (high-low) * raw

def extract_data(obj):
  x_center, y_center, width, height = obj["bbox_center"][0]

  center_range = [0.4, 0.6] # 0.5 is always the image center

  if center_range[0] <= x_center <= center_range[1]:
    obj["direction"] = "center"
  elif 0.2 < x_center < center_range[0]:
    obj["direction"] = "left"
  elif x_center <= 0.2:
    obj["direction"] = "extreme left"
  elif center_range[1] < x_center < 0.8:
    obj["direction"] = "right"
  else:
    obj["direction"] = "extreme right"


  obj["distance"] = (width * height)**0.5
  obj["width"] = width
  obj["y_center"] = y_center
  obj["direction_score"] = direction_score(x_center)

  return obj

def get_proximity(obj):
  distance = obj["distance"]
  obstruction = obj["width"]
  y2 = obj["bbox"][0][3]

  bias = bottom_bias(y2)
  distance = 0.7 * distance + 0.3 * obstruction

  proximity = min(distance * bias, 1)

  return proximity


# In[ ]:


def tick_frame():
  global frame_counter
  frame_counter +=1

def update_state(track_id, proximity):

  if track_id is None:
    return "new"

  if track_id not in tracking_hist:
    tracking_hist[track_id] = deque(maxlen = history_len)

  tracking_hist[track_id].append((proximity, frame_counter))

  hist = tracking_hist[track_id]

  if len(hist) < 3:
    return "new"

  recent = [p for p,_ in list(hist)[-3:]]
  older = [p for p,_ in list(hist)[-6:-3]]

  if not older:
    return "new"

  delta_change = ((sum(recent)/len(recent)) - (sum(older)/len(older)))

  if delta_change > approaching_threshold:
    return "approaching"
  elif delta_change < -receding_threshold:
    return "receding"
  else:
    return "stationary"

def prune_stale_tracks(active_ids):
  stale =[]

  for track_id, hist in tracking_hist.items():
    if track_id not in active_ids:
      last_frame = hist[-1][1]

      stale_for = frame_counter - last_frame
      if stale_for > 10:
        stale.append(track_id)

  for track_id in stale:
    tracking_hist.pop(track_id, None)



def should_alert(track_id, proximity, state):
  if track_id is None:
    return True

  if track_id not in announced:
    return True

  prev = announced.get(track_id)

  has_moved = abs(proximity - prev["proximity"]) >= 0.3
  has_changed_state = state != prev["state"]

  if has_moved or has_changed_state:
    return True

  return False

def prune_announced():
  stale = []
  tracking = list(tracking_hist.keys())
  for track_id in announced:
    if track_id not in tracking:
      stale.append(track_id)

  for track_id in stale:
    announced.pop(track_id, None)


def detect_objects(image):

  tick_frame()
  active_ids = set()
  confidence_threshold=0.5
  results=model.track(image,
                      conf= confidence_threshold,
                      classes = allowed_classes,
                      tracker = "bytetrack.yaml",
                      persist = True,
                      verbose = False)
  r=results[0]

  objects=[]
  for box in r.boxes:
    track_id = int(box.id[0]) if box.id is not None else None

    if track_id is not None:
      active_ids.add(track_id)

    obj = {
          "track_id": track_id,
          "class_id": int(box.cls[0]),
          "class_name": r.names[int(box.cls[0])],
          "confidence": float(box.conf[0]),
          "bbox": box.xyxyn.tolist(),
          "bbox_center": box.xywhn.tolist()
        }
    obj = extract_data(obj)
    obj["proximity"] = get_proximity(obj)
    obj["state"] = update_state(track_id, obj["proximity"])
    if should_alert(track_id, obj["proximity"], obj["state"]):
      objects.append(obj)

  prune_stale_tracks(active_ids)
  prune_announced()

  objects.sort(key= lambda x: x["proximity"], reverse=True)

  return objects


# In[ ]:


def get_state_multiplier(state):
  if state == "approaching":
    return 1.3
  elif state == "receding":
    return 0.7
  else:
    return 1

def group_objects(candidates):
  grouped = []
  counts = {}
  seen = set()

  for obj in candidates:
    slot = (obj["direction"], obj["class_name"])

    if slot in seen:
      counts[slot] += 1
    else:
      counts[slot] = 1
      seen.add(slot)
      grouped.append(obj)

  return grouped, counts

def select_objects(objects):
  urgency_threshold = 0.15
  max_urgency = 1.82 # a train approaching dead ahead with proximity 1 (i.e. touching the user).

  emergency_proximity = 0.75

  for obj in objects:
    proximity = obj["proximity"]
    direction_score = obj["direction_score"]
    state = obj["state"]
    danger_weight, min_proximity = class_profile[obj["class_name"]]

    if proximity >= emergency_proximity and danger_weight >= 1.0:
      obj["urgency"] = 1.0  # for fast moving objects that cannot be detected across frames
      continue

    if state == "approaching":
      min_proximity = min_proximity * 0.5
    elif state == "receding":
      min_proximity = min_proximity * 1.5


    if proximity < min_proximity:
      obj["urgency"] = 0
      continue

    state_multiplier = get_state_multiplier(state)

    urgency = proximity * state_multiplier * direction_score * danger_weight


    obj["urgency"] = urgency / max_urgency

  objects.sort(key = lambda x: x["urgency"], reverse=True)
  candidates = [o for o in objects if o["urgency"] >= urgency_threshold]
  grouped_candidates, counts = group_objects(candidates)

  return grouped_candidates[:3], counts


def get_proximity_label(proximity):
  if proximity >= 0.75:
    return "very close"
  else:
    return ""


# In[ ]:


def TTS_sentence(candidates, counts):
  sentences = []

  for obj in candidates:
    class_name = obj["class_name"]
    state = state_label.get(obj["state"])
    proximity_label = get_proximity_label(obj["proximity"])
    direction = direction_label.get(obj["direction"])
    slot = (obj["direction"], class_name)
    num = counts.get(slot)

    class_str = f"{num} {class_name}s" if num > 1 else class_name

    parts = [direction, class_str]

    if proximity_label:
      parts.append(proximity_label)
    if state:
      parts.append(state)

    s = ", ".join(parts)
    sentences.append(s)

  return sentences

def mark_announced(candidates):
  for obj in candidates:
    announced[obj["track_id"]] = {
        "proximity": obj["proximity"],
        "state": obj["state"]
    }

def notify(objects):
  candidates, counts = select_objects(objects)
  mark_announced(candidates)
  sentences = TTS_sentence(candidates, counts)
  return sentences


# In[ ]:


def tts_worker():

  pythoncom.CoInitialize()
  speaker = win32com.client.Dispatch("SAPI.SpVoice")
  speaker.Rate = 2
  voices = speaker.GetVoices()

  if voices.Count > 1:
    speaker.Voice = voices.Item(1)


  while True:
    sentence = tts_queue.get()

    if not sentence:
      break
    
    speaker.Speak(sentence)
    tts_queue.task_done()

tts_thread = threading.Thread(target = tts_worker, daemon = True)
tts_thread.start()

prev_s = ""

def speak(sentences):
  global prev_s
  for s in sentences:
    if tts_queue.empty():
      if prev_s != s:
        prev_s = s
        tts_queue.put(s)


# In[ ]:


def object_detection_system(frame):

    objects = detect_objects(frame) 
    sentences = notify(objects)
    speak(sentences)

    return sentences

