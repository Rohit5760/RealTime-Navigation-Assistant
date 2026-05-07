#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import cv2
from object_detection_functions import object_detection_system


# In[ ]:

cap = cv2.VideoCapture(0)
frame_skip = 3
frame_idx = 0 

while cap.isOpened():
    cap.grab()
    ret, frame = cap.retrieve()
    if not ret:
        break

    frame_idx +=1
    if frame_idx % frame_skip !=0:
        continue

    sentences = object_detection_system(frame)

    for s in sentences:
        print(s)

cap.release()

