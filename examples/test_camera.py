import cv2

max_index = 10
cameras = []
for index in range(max_index):
    try:
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            print("Camera Index:", index)
            cap.release()
    except:
        print("ERROR")