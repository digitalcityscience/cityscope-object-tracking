import pyrealsense2 as rs
import numpy as np
import cv2
import cv2.aruco as aruco
import time
import math
import json
import socket
import random


font = cv2.FONT_HERSHEY_SIMPLEX
kernel = np.array([[-1,-1,-1],
                    [-1, 9,-1],
                    [-1,-1,-1]])
buildingDict = {}

loop = 16
exposure = 4000
selectedPoint = 0

#[width, height]
pts_src = np.array([[0, 0], [0, 1080], [1920, 0],[1920, 1080]])
pts_dst = np.array([[0, 0], [0, 2000], [2000, 0],[2000, 2000]])



class building:
    def __init__(self, id, pos, lastSeen):
        self.id = id
        self.pos = pos
        self.confidence = 0
        self.lastSeen = lastSeen

    def updateConfidence(self, currentLoop):
        self.confidence = currentLoop -self.lastSeen

    def updatePosition(self,pos):
        self.pos = pos
        self.lastSeen = loopcount

    def getConfidence(self):
        return self.confidence

    def getPos(self):
        return self.pos

    def getID(self):
        return self.id


def rotate(xy, theta):
    # https://en.wikipedia.org/wiki/Rotation_matrix#In_two_dimensions
    cos_theta, sin_theta = math.cos(theta), math.sin(theta)

    return (
        xy[0] * cos_theta - xy[1] * sin_theta,
        xy[0] * sin_theta + xy[1] * cos_theta
    )

def translate(xy, offset):
    return xy[0] + offset[0], xy[1] + offset[1]

def printJSON(data):
    jsonDict = {}
    parentDict ={}

    for i in data:
        jsonDict[i] = data[i].getPos()

    parentDict["table_state"] = jsonDict
    return jsonDict

def normalizeCorners(corner):
    coords = corner
    pts = coords.reshape((-1,1,2))

    p1 = tuple(pts[0][0])
    p4 = tuple(pts[2][0])

    ctrX = (p1[0] + p4[0]) / 2
    ctrY = (p1[1] + p4[1]) / 2

    dx = p1[0] - ctrX
    dy = p1[1] - ctrY

    angle = math.atan2(dy,dx)
    angleDeg = math.degrees(angle)

    ctrX = np.interp(ctrX,[0,10000],[0,10000])
    ctrY = np.interp(ctrY,[0,10000],[0,100000])

    returnData = [int(ctrX),int(ctrY), angleDeg]
    return returnData

def handleKeypress(key):
    if key == 2424832:
        print("left")
        pts_src[selectedPoint, 0] += 10
    if key == 2490368:
        print("up")
        pts_src[selectedPoint, 1] += 10
    if key == 2555904:
        print("right")
        pts_src[selectedPoint, 0] -= 10
    if key == 2621440:
        print("down")
        pts_src[selectedPoint, 1] -= 10



#Realsense Config
#--------------------------------------------
pipeline = rs.pipeline()
config = rs.config()
#config.enable_device('001622070380')
config.enable_stream(rs.stream.color, 1920, 1080, rs.format.rgb8, 30)

#config.enable_stream(rs.stream.infrared, 2, 1280 , 720, rs.format.y8, 30)
profile = pipeline.start(config)

s = profile.get_device().query_sensors()[1]
s.set_option(rs.option.exposure, 650)

IR1_stream = profile.get_stream(rs.stream.color, 0) # Fetch stream profile for depth stream
frames = pipeline.wait_for_frames()

loopcount = 0
lastUpdatedTime = time.time()
lastSentTime = time.time()

pts_src = np.loadtxt(open("homography.txt"))
print("Homography loaded")


HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 8052        # Port to listen on (non-privileged ports are > 1023)

wheelPosX = 0
wheelPosY = 0

while True:
    print("starting socket")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()

        conn, addr = s.accept()
        with conn:
            print('Connected by', addr)

            while conn:
                    if loop > 32: #neuer Loop
                        loop = 16
                        loopcount += 1
                    else:
                        try:
                            #ir_sensor.set_option(rs.option.gain, gain)
                            loop += 4
                            #print("TTS: ",(time.time() - start_time) * 1000) # F^^
                        except:
                            loopcount -= 1

                    try:
                        frames = pipeline.wait_for_frames()
                        ir_data  = frames.get_color_frame() 
                    except:
                        "Frame Aquisition Error"
                        continue

                    if not ir_data:
                        continue

                    for x in list(buildingDict):
                        buildingDict[x].updateConfidence(loopcount)
                        if buildingDict[x].getConfidence() > 5: #if not found after 5 loops, discard
                            buildingDict.pop(x)


                    ir_image = np.asanyarray(ir_data.get_data())
                    #ir_image = ir_image[0:1000, 0:1000]
                   # ir_image = cv2.cvtColor(ir_image,cv2.COLOR_GRAY2BGR)
                    ir_image = cv2.filter2D(ir_image, -1, kernel)
                    h, state = cv2.findHomography(pts_src, pts_dst)
                    ir_image = cv2.warpPerspective(ir_image, h, (2000, 2000))

                    aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_250)
                    parameters = aruco.DetectorParameters_create()
                    parameters.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX

                    parameters.maxMarkerPerimeterRate = 0.2
                    parameters.minMarkerPerimeterRate =0.05
                    parameters.polygonalApproxAccuracyRate = 0.03

                    parameters.minOtsuStdDev = 2.0
                    parameters.perspectiveRemovePixelPerCell = 10
                    parameters.perspectiveRemoveIgnoredMarginPerCell = 0.13
                    parameters.errorCorrectionRate = 0.3

                    parameters.adaptiveThreshWinSizeMin = 3
                    parameters.adaptiveThreshWinSizeMax = 23
                    parameters.adaptiveThreshWinSizeStep = 5
                    parameters.adaptiveThreshConstant = 7

                    # ir_image = np.hstack((ir_image,ir_image))
                    # ir_image = np.vstack((ir_image,ir_image))
                    corners, ids, rejectedImgPoints  = aruco.detectMarkers(ir_image, aruco_dict, parameters=parameters)


                    if ids is not None:
                        for i in range(0,len(ids)):
                            markerID = int(ids[i])

                            if markerID is not 500:
                                pos = normalizeCorners(corners[i])

                                if markerID not in buildingDict:
                                    buildingDict[markerID] = building(int(ids[i]), pos, loopcount)

                                else:
                                    buildingDict[markerID].updatePosition(pos)
                                    #lastPos = buildingDict[markerID].getPos()
                                    #diff = np.subtract(pos[0], lastPos[0])
                                    #absDiff = abs(np.sum(diff))
                                    #if absDiff > 5:
                                    #  buildingDict[markerID].updatePosition([pos[0], pos[1]])
                                # else:
                                    # buildingDict[markerID].updatePosition([lastPos[0], pos[1]])

                    status = np.zeros((800,320,3), np.uint8)
                    ir_image = aruco.drawDetectedMarkers(ir_image, corners, borderColor = (0,255,0))
                    ir_image = aruco.drawDetectedMarkers(ir_image, rejectedImgPoints, borderColor = (0,0,255))

                    for i in buildingDict:
                        id = buildingDict[i].getID()
                        pos =  buildingDict[i].getPos()
                        angle = pos[1]
                        ctr = pos[0]

                    if (time.time() - lastSentTime) > 0.05:
                        lastSentTime = time.time()

                        jsonString= json.dumps(printJSON(buildingDict))
                        #print(jsonString)
                        b = jsonString.encode('utf-8')
                        lastSentTime = time.time()
                        try:
                            conn.sendall(b)
                        except:
                            break


                    statusX = 50
                    
                    for i in range(0,ir_image.shape[0], 50):
                            ir_image = cv2.line(ir_image,(0,i), (ir_image.shape[1], i), (255,255,255), 1)
                            i += 10
                    for j in range(0,ir_image.shape[1],50):
                            ir_image = cv2.line(ir_image,(j,0), (j,ir_image.shape[1]), (255,255,255), 1)
                            j += 10
                            
                    for x in buildingDict:
                        ctr = buildingDict[x].getPos()[0]
                        deg = buildingDict[x].getPos()[1]
                        id = buildingDict[x].getID()
                        conf = buildingDict[x].getConfidence()

                        cv2.putText(status, str(id), (30, statusX), font,0.8,(255,255,255),1)
                        cv2.putText(status, str(ctr),(100,statusX),font,0.6,(255,255,255),1)
                        cv2.putText(status, str(int(deg * 180/3.14)),(220,statusX),font,0.6,(255,255,255),1)
                        cv2.putText(status, str(conf),(300,statusX),font,0.6,(255,255,255),1)
                        statusX += 35

                    imS = cv2.resize(ir_image, (1000, 1000))  
                    cv2.namedWindow('IR', cv2.WINDOW_AUTOSIZE)
                    cv2.namedWindow('Status', cv2.WINDOW_AUTOSIZE)
                    cv2.imshow('IR', imS)
                    cv2.imshow('Status', status)


                    key = cv2.waitKeyEx(1)

                    if key == 32:
                            print("Homography dumped") 
                            np.savetxt("homography.txt", pts_src, fmt="%s")

                    if key == ord('l'):
                        pts_src = np.loadtxt(open("homography.txt"))
                        print("Homography loaded")
                    if key == ord('1'):
                        selectedPoint = 0
                        print("point 1")
                    if key == ord('2'):
                        selectedPoint = 1
                        print("point 2")
                    if key == ord('3'):
                        selectedPoint = 2
                        print("point 3")
                    if key == ord('4'):
                        selectedPoint = 3
                        print("point 4")
                    elif key is not -1:
                            handleKeypress(key)

            s.close()
            print("conn was aparrently closed!")
                    


