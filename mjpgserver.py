#Copyright 2017 Tony Speer under MIT License
from bottle import route, run, template, response
import requests, threading, struct, time
from collections import namedtuple


class Mjpeg:
    def __init__(self, url):
        self.url = url
        self.image = ""
        self.stopWork = False

    def doWork(self):
        global lastRequest
        r = requests.get(self.url, stream=True)
        print self.url
        print r.status_code
        print r.headers['content-type']
        if r.headers["content-type"] == "application/octet-stream": #wvc200 mode
            wvc = True
            Header = namedtuple("header", "magic framesize framewidth frameheight frameoffset chunksize unknown")
            header = None
            img = ""
        else:
            wvnc = False

        x = 0
        data = ""
        for line in r.iter_content(chunk_size=1024):
            if self.stopWork or time.time() - lastRequest > 15:
                print "Stopping work..."
                self.image = ""
                break

            if line:
                data += line
                if wvc:
                    if len(data) < 48 and header == None: #We need the header but don't have enough data.
                        continue
                    elif header == None: #Get the header
                        #header size 4 + 4 + 2 + 2 + 4 + 2 + 30 = 48
                        header = Header._make(struct.unpack("4sIHHIH30s", data[:48]))
                        
                        data = data[48:]

                        if header.frameoffset == 0: #New frame
                            img = ""
                            framesize = header.framesize

                        if header.magic != "MJPG":
                            print "Failed to get header."
                            break

                    else: #Get the image
                        if len(data) < header.chunksize:
                            #print "Need more data."
                            continue
                        else:
                            img += data[:header.chunksize]
                            data = data[header.chunksize:] #Remove used chunk from data
                            header = None
                            if len(img) == framesize:
                                self.image = img

                else: #Normal MJPG mode
                    a = data.find(b'\xff\xd8')
                    b = data.find(b'\xff\xd9')
                    if a != -1 and b != -1:
                        if len(data[a:b+2]) > 0:
                            self.images = data[a:b+2]
                        data = data[b+2:] #Trim data

cam = Mjpeg("http://192.168.1.27/img/video.mjpeg")

def worker():
    global cam, go, lastRequest
    while go:
        if time.time() - lastRequest < 15: #Don't do work if no one has request an image.
            cam.doWork()

        time.sleep(0.01)

go = True
lastRequest = time.time()

threads = []
t = threading.Thread(target=worker)
threads.append(t)
t.start()

@route("/image")
def image():
    global cam, lastRequest
    lastRequest = time.time()

    if cam.image == "": #If there is no image. Wait for 5 seconds.
        startWait = time.time()
        while cam.image == "" and time.time() - startWait < 5:
            time.sleep(0.25)

    if cam.image == "":
        return "Failed to get image."

    response.content_type = "image/jpeg"
    return cam.image

try:
    run(host="0.0.0.0", port=5001)
finally:
    cam.stopWork = True
    go = False

           
