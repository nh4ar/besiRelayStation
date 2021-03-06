
import numpy
import os
import shutil
import datetime
import time
import rNTPTime
from Constants import *
import testFeatureSending

def main():
	motionFeatExt()

def motionPreProcessing(dataSample):
	dataSample = float(dataSample)

	clippingValue = 4000
	if abs(dataSample) >= clippingValue:
		dataSample = clippingValue*(dataSample/abs(dataSample))

	dataSample = (dataSample+4000)/8000 * 100;

	return dataSample

def clipping(data, t):
	# new_data = [x for _,x in sorted(zip(t,data))]
	new_data = data
	size = 2
	# print data
	data_idx = numpy.where(numpy.abs(data)>=99)
	data_idx = numpy.array(data_idx)
	data_idx = data_idx[0]

	for k in range(len(data_idx)):
		if (data_idx[k]>size and data_idx[k]<len(new_data)-size):
			new_data[data_idx[k]] = numpy.median(data[(data_idx[k]-size):(data_idx[k]+size)])
	
	return new_data

def readConfigFile():
	# get BS IP and RS port # from config file
	configFileName = r'/root/besi-relay-station/BESI_LOGGING_R/config'
	fconfig = open(configFileName)
	for line in fconfig:
		if line[0] == "#":
			pass
		else:
			splitLine = line.split("=")
			try:
				if splitLine[0] == "BaseStation_IP":
					BaseStation_IP2 = str(splitLine[1]).rstrip()
			except:
				print "Error reading IP Address"
			
			try:
				if splitLine[0] == "relayStation_ID":
					relayStation_ID2 = int(splitLine[1])
			except:
				print "Error reading Port" 
			try:
				if splitLine[0] == "PebbleFolder":
					PebbleFolder = str(splitLine[1]).rstrip()
			except:
				print "Error reading Pebble Folder"
			# try:
			# 	if splitLine[0] == "Wearable":
			# 		wearable_mode = str(splitLine[1]).rstrip()
			# 		if wearable_mode=="Pixie":
			# 			IS_PIXIE = True
			# 			IS_MEMINI = False
			# 		elif wearable_mode=="Memini":
			# 			IS_PIXIE = False
			# 			IS_MEMINI = True
			# except:
			# 	print "Error finding Pebble Mode"

			# if IS_PIXIE == True:
				
	default_settings = ''
	fconfig.close()

	return BaseStation_IP2, relayStation_ID2, PebbleFolder

def fftpower(data):
	Fs = float(50) #sampling freq
	Ts = 1/Fs #period
	L = float(len(data))
	# print "Ts=" +str(Ts)
	# print "L="+str(L)

	f = Fs*numpy.arange(-(L/2),(L/2)-1)/L

	Y = numpy.abs(numpy.fft.fft(data))
	PY = (Y**2)/(L*Fs)
	PY = PY*2
	# print "PY=" +str(PY)

	Pf = f[numpy.where(f>=0)]
	# print "Pf=" +str(Pf)

	PY1 = PY[numpy.where((Pf>0.1) & (Pf<=0.5))]
	PY1mean = numpy.mean(PY1)
	PY1max = max(PY1)
	# print "PY1max=" +str(PY1max)

	PY2 = PY[numpy.where((Pf>0.5) & (Pf<=3))]
	PY2mean = numpy.mean(PY2)
	PY2max = max(PY2)

	PY3 = PY[numpy.where((Pf>3) & (Pf<=10))]
	PY3mean = numpy.mean(PY3)
	PY3max = max(PY3)

	return PY1mean, PY1max, PY2mean, PY2max, PY3mean, PY3max

def medfilt (x, k):
    """Apply a length-k median filter to a 1D array x.
    Boundaries are extended by repeating endpoints.
    """
    # assert k % 2 == 1, "Median filter length must be odd."
    # assert x.ndim == 1, "Input must be one-dimensional."
    k2 = (k - 1) // 2
    y = numpy.zeros ((len (x), k))
    y[:,k2] = x
    for i in range (k2):
        j = k2 - i
        y[j:,i] = x[:-j]
        y[:j,i] = x[0]
        y[:-j,-(i+1)] = x[j:]
        y[-j:,-(i+1)] = x[-1]
    return numpy.median (y, axis=1)

def teagerCompute(x):

	# x = medfilt(x,5)
	size_x = len(x)
	VL = 2 #for point-wise teager
	k = len(x)

	start_point=(VL/2)-1
	yy=numpy.zeros(size_x)
	
	#for 1:1
	temp_a = numpy.dot(x[2:k-1],x[2:k-1]) - numpy.dot(x[3:k],x[1:k-2])
	yy[2:k-1] = yy[2:k-1]+temp_a
	#end for
	
	yy[1] = yy[2]
	yy[-1] = yy[-2]
	y = numpy.abs(yy)

	return y

# def motionFeatExt(startDateTime, hostIP, BASE_PORT, pebbleFolder):
def motionFeatExt():

		debugMode = True

		#get info from config file
		hostIP, BASE_PORT, pebbleFolder = readConfigFile()

		#for realtime processing - when restarted - move every older motion data to rawPebble
		files = os.walk(BASE_PATH + pebbleFolder + "/").next()[2] #BASE_PATH = /media/card/

		# Comment out for testing
		for names in files:
			try: 
				src = BASE_PATH + pebbleFolder + "/"+names
				dst = BASE_PATH + "Relay_Station" + str(BASE_PORT) + "/rawPebble/" + files[0]
				shutil.move(src,dst)
			except:
				continue
		print "init realtime PebbleFeature Ext.."

		x=[]
		y=[]
		z=[]


		rawTime=[]
		rawX=[]
		rawY=[]
		rawZ=[]

		max_x_values=[]
		min_x_values=[]
		mean_x_values=[]
		max_y_values=[]
		min_y_values=[]
		mean_y_values=[]
		max_z_values=[]
		min_z_values=[]
		mean_z_values=[]

		iterations = 0
		HB_Pixie_Value = 0

		windowSize = 3000 #50Hz*60sec = 1min
		stepSize = windowSize/2

		server_address = (hostIP, BASE_PORT)

		startReadLine = 1 #line0 = header, line1 = startline on the rawPebble file
		currLine = startReadLine #init current read line as the start line
		
		FeatureList = ("timestamp_1,timestamp_2,"
		+"x_mean,x_median,x_max,x_var,x_rms,x_IQR,x_meanXrate,x_meanDiff,x_maxDiff,x_teager_mean,x_teager_std,"
		+"x_teager_max,x_fft_mean_0_1,x_fft_0_1_max,x_fft_mean_1_3,x_fft_1_3_max,x_fft_mean_3_10,x_fft_3_10_max,"
		+"y_mean,y_median,y_max,y_var,y_rms,y_IQR,y_meanXrate,y_meanDiff,y_maxDiff,y_teager_mean,y_teager_std,"
		+"y_teager_max,y_fft_mean_0_1,y_fft_0_1_max,y_fft_mean_1_3,y_fft_1_3_max,y_fft_mean_3_10,y_fft_3_10_max,"
		+"z_mean,z_median,z_max,z_var,z_rms,z_IQR,z_meanXrate,z_meanDiff,z_maxDiff,z_teager_mean,z_teager_std,"
		+"z_teager_max,z_fft_mean_0_1,z_fft_0_1_max,z_fft_mean_1_3,z_fft_1_3_max,z_fft_mean_3_10,z_fft_3_10_max,"
		+"mag_mean,mag_median,mag_max,mag_var,mag_rms,mag_IQR,mag_meanXrate,mag_meanDiff,mag_maxDiff,mag_teager_mean,mag_teager_std,"
		+"mag_teager_max,mag_fft_mean_0_1,mag_fft_0_1_max,mag_fft_mean_1_3,mag_fft_1_3_max,mag_fft_mean_3_10,mag_fft_3_10_max,"
		+"corr_xy,corr_xz,corr_yz"
		+"\n")

		#Fs = 50.0;  # sampling rate
		#Ts = 1.0/Fs; # sampling interval
		#t = numpy.arange(0,1,Ts) # time vector

		while True:

				# Get file name to open
				files = os.walk(BASE_PATH + pebbleFolder + "/").next()[2] #BASE_PATH = /media/card/
				files.sort() #previous file first

				if (len(files) > 0) : #not an empty folder

					#Generate destination file
					#Convert Epoch time -> readable Time 
					dstFileTime = files[0].split('_')
					dstFileTime = dstFileTime[2].split('.')
					dstFileTime = datetime.datetime.fromtimestamp(int(dstFileTime[0])/1000)
					dstFileTime = dstFileTime - datetime.timedelta(hours=4) #ET time
					dstFileTime = dstFileTime.strftime('%y-%m-%d_%H-%M-%S')

					PebbleFeatureFileName = BASE_PATH+"Relay_Station{0}/PebbleFeature/PebbleFeature{1}.txt".format(BASE_PORT, dstFileTime)
					#check if the PebbleFeature has already been created 
					# if not os.path.exists(BASE_PATH + pebbleFolder + "/" +files[0]):
					if not os.path.exists(PebbleFeatureFileName):
						with open(PebbleFeatureFileName, "w") as PebbleFeatureFile:
							PebbleFeatureFile.write(dstFileTime+"\n")
							PebbleFeatureFile.write("Deployment ID: Unknown, Relay Station ID: {}\n".format(BASE_PORT))
							# PebbleFeatureFile.write("timestamp_1,timestamp_2,x_max,x_min,x_mean,x_std,x_fft_mean,x_fft_0_1_max,x_fft_mean_0_1,x_fft_1_3_max,x_fft_mean_1_3,x_fft_3_10_max,x_fft_mean_3_10,x_teager_mean,x_teager_max,y_max,y_min,y_mean,y_std,y_fft_mean,y_fft_0_1_max,y_fft_mean_0_1,y_fft_1_3_max,y_fft_mean_1_3,y_fft_3_10_max,y_fft_mean_3_10,y_teager_mean,y_teager_max,z_max,z_min,z_mean,z_std,z_fft_mean,z_fft_0_1_max,z_fft_mean_0_1,z_fft_1_3_max,z_fft_mean_1_3,z_fft_3_10_max,z_fft_mean_3_10,z_teager_mean,z_teager_max")
							PebbleFeatureFile.write(FeatureList)
							# PebbleFeatureFile.write("x_max,x_min,x_mean,x_std,x_fft_mean,x_fft_0_1_max,x_fft_1_3_max,x_fft_3_10_max,x_teager_mean,x_teager_max,y_max,y_min,y_mean,y_std,y_fft_mean,y_fft_0_1_max,y_fft_1_3_max,y_fft_3_10_max,y_teager_mean,y_teager_max,z_max,z_min,z_mean,z_std,z_fft_mean,z_fft_0_1_max,z_fft_1_3_max,z_fft_3_10_max,z_teager_mean,z_teager_max\n ")
						# PebbleFeatureFile.close()

					f = open(BASE_PATH + pebbleFolder + "/" + files[0], "r") 
					rawlineCount = 0
					for numLines in f.xreadlines(  ): rawlineCount += 1 # read #of lines
					f.close()

					if debugMode: print "reading lines from " + files[0]
					if debugMode: print "rawlineCount =" + str(rawlineCount)

					if rawlineCount > currLine:			

						if debugMode: print "length of rawX,Y,Z = " + str(len(rawX))

						with open(BASE_PATH + pebbleFolder + "/" + files[0], "r") as rawPebble:
							# for i in range(currLine, rawlineCount):

							rawPebbleData = rawPebble.readlines()[currLine:rawlineCount]

							for i in range(len(rawPebbleData)): #rawPebbleData[i] = z,y,x,time, rawPebbleData = [{z,y,x,time}; {z,y,x,time}...]

								num = rawPebbleData[i].split(',')
								if len(num) >= 4:
									rawZ.append(motionPreProcessing(int(num[0]))) 
									rawY.append(motionPreProcessing(int(num[1])))
									rawX.append(motionPreProcessing(int(num[2])))
									rawTime.append(int(num[3])) 
									# rawTime.append(int(num[4])) #for P2D4
									# print num[0] +" "+num[1] +" "+ num[2] +" "+ num[3]

							currLine = rawlineCount
							if debugMode: print "currLine = " +str(currLine)


					elif (len(files) >= 2) : #rawlineCount == or < currLine
						if debugMode: print "length of rawX,Y,Z = " + str(len(rawX))
						currLine = startReadLine # re-init currLine

						#Move the finished file
						src = BASE_PATH + pebbleFolder + "/"+files[0]
						dst = BASE_PATH + "Relay_Station" + str(BASE_PORT) + "/rawPebble/" + files[0]

						shutil.move(src,dst)
						if debugMode: print "finished reading "+ files[0]+", moving file now.."

						files = os.walk(BASE_PATH + pebbleFolder + "/").next()[2] #BASE_PATH = /media/card/
						files.sort() # re-read file names

						#Generate destination file
						#Convert Epoch time -> readable Time 
						dstFileTime = files[0].split('_')
						dstFileTime = dstFileTime[2].split('.')
						dstFileTime = datetime.datetime.fromtimestamp(int(dstFileTime[0])/1000)
						dstFileTime = dstFileTime - datetime.timedelta(hours=4) #ET time
						dstFileTime = dstFileTime.strftime('%y-%m-%d_%H-%M-%S')

						PebbleFeatureFileName = BASE_PATH+"Relay_Station{0}/PebbleFeature/PebbleFeature{1}.txt".format(BASE_PORT, dstFileTime)
						with open(PebbleFeatureFileName, "w") as PebbleFeatureFile:
								PebbleFeatureFile.write(dstFileTime+"\n")
								PebbleFeatureFile.write("Deployment ID: Unknown, Relay Station ID: {}\n".format(BASE_PORT))
								PebbleFeatureFile.write(FeatureList)

						time.sleep(1)

					elif (len(files) == 1) and (currLine==rawlineCount) :
						if debugMode: print "waiting for new data..."
						# if debugMode: print "length of rawX = " + str(len(rawX))
						time.sleep(1)

				#finished reading # of lines of the first file

				else: # no new pebble motion data file
					pass #continue to check if buffer >= 3000 sample or not
					# time.sleep(5)

				# if (False) :
				while ((len(rawX)>=windowSize+50) and (len(rawY)>=windowSize+50) and (len(rawZ)>=windowSize+50)) :
					if debugMode: print "Feature Extracting.."
					if debugMode: print "data length = " + str(len(rawX))

					#for pre-processing
					x = rawX[0:windowSize] #from 0 to 3000 + safety 50 samples (in case some processing needs the sample# 3001)
					y = rawY[0:windowSize]
					z = rawZ[0:windowSize]

					x = clipping(x, rawTime[0:windowSize])
					y = clipping(y, rawTime[0:windowSize])
					z = clipping(z, rawTime[0:windowSize])
					x = medfilt(x,5)
					y = medfilt(y,5)
					z = medfilt(z,5)

					# if debugMode: print numpy.diff(rawTime[0:3050])

					# x,y,z = motionPreProcessing(x,y,z,rawTime[0:3050])
					mag = numpy.sqrt(numpy.square(x) + numpy.square(y) + numpy.square(z))

					lower_lim = 1 #some feature required data[lower_lim-1]
					upper_lim = windowSize #3000

					timestamp_1 = rawTime[lower_lim]
					timestamp_2 = rawTime[upper_lim]

					Fs = 50.0;  # sampling rate
					Ts = 1.0/Fs; # sampling interval
					t = numpy.arange(0,1,Ts) # time vector
					n = 3000 # length of the signal
					k = numpy.arange(n)
					T = n/Fs
					frq = k/T # two sides frequency range
					frq = frq[range(n/2)] # one side frequency range

					##### frequency #####
					x_fft_mean_0_1,x_fft_0_1_max,x_fft_mean_1_3,x_fft_1_3_max,x_fft_mean_3_10,x_fft_3_10_max = fftpower(x)
					y_fft_mean_0_1,y_fft_0_1_max,y_fft_mean_1_3,y_fft_1_3_max,y_fft_mean_3_10,y_fft_3_10_max = fftpower(y)
					z_fft_mean_0_1,z_fft_0_1_max,z_fft_mean_1_3,z_fft_1_3_max,z_fft_mean_3_10,z_fft_3_10_max = fftpower(z)
					mag_fft_mean_0_1,mag_fft_0_1_max,mag_fft_mean_1_3,mag_fft_1_3_max,mag_fft_mean_3_10,mag_fft_3_10_max = fftpower(mag)
					#####
					x_fft_mean_3_10 = x_fft_mean_3_10
					y_fft_mean_3_10 = y_fft_mean_3_10*1.4
					z_fft_mean_3_10 = z_fft_mean_3_10*1.5
					mag_fft_mean_3_10 = mag_fft_mean_3_10*2

					##### teagers #####
					x_teager = teagerCompute(x)
					y_teager = teagerCompute(y)
					z_teager = teagerCompute(z)
					mag_teager = teagerCompute(mag)

					x_teager_max = max(x_teager)
					x_teager_mean = numpy.mean(x_teager)/Fs+9
					y_teager_max = max(y_teager)
					y_teager_mean = numpy.mean(y_teager)/Fs+9  
					z_teager_max = max(z_teager)
					z_teager_mean = numpy.mean(z_teager)/Fs+15
					mag_teager_max = max(mag_teager)
					mag_teager_mean = numpy.mean(mag_teager)/Fs*1.25+25

					x_teager_std = numpy.std(x_teager, ddof=1)+8
					y_teager_std = numpy.std(y_teager, ddof=1)*1.6+8
					z_teager_std = numpy.std(z_teager, ddof=1)*1.5+15
					mag_teager_std = numpy.std(mag_teager, ddof=1)*2.6+15
					#####

					##### x features #####
					x_max = max(x[lower_lim:upper_lim])
					x_mean = numpy.mean(x[lower_lim:upper_lim])
					x_median = numpy.median(x[lower_lim:upper_lim])
					x_var = numpy.var(x[lower_lim:upper_lim])
					x_rms = numpy.sqrt(numpy.mean(numpy.square(x[lower_lim:upper_lim])))
					x_IQR = numpy.subtract(*numpy.percentile(x[lower_lim:upper_lim], [75, 25]))
					#Mean x Rate
					xArray = numpy.array(x[lower_lim:upper_lim])
					xArray = xArray - x_mean
					x_meanXrate = 2*(numpy.diff(numpy.sign(xArray)) != 0).sum() #ZeroCrossingRate = when x[-1]*x[0] changes sign
					x_meanDiff = numpy.mean(numpy.diff(x[lower_lim:upper_lim]))
					x_maxDiff = max(numpy.diff(x[lower_lim:upper_lim]))

					##### y features #####
					y_max = max(y[lower_lim:upper_lim])
					y_mean = numpy.mean(y[lower_lim:upper_lim])
					y_median = numpy.median(y[lower_lim:upper_lim])
					y_var = numpy.var(y[lower_lim:upper_lim])
					y_rms = numpy.sqrt(numpy.mean(numpy.square(y[lower_lim:upper_lim])))
					y_IQR = numpy.subtract(*numpy.percentile(y[lower_lim:upper_lim], [75, 25]))
					#Mean x Rate
					yArray = numpy.array(y[lower_lim:upper_lim])
					yArray = yArray - y_mean
					y_meanXrate = (numpy.diff(numpy.sign(yArray)) != 0).sum()*2.5 #ZeroCrossingRate = when x[-1]*x[0] changes sign
					y_meanDiff = numpy.mean(numpy.diff(y[lower_lim:upper_lim]))
					y_maxDiff = max(numpy.diff(y[lower_lim:upper_lim]))

					##### z features #####
					z_max = max(z[lower_lim:upper_lim])
					z_mean = numpy.mean(z[lower_lim:upper_lim])
					z_median = numpy.median(z[lower_lim:upper_lim])
					z_var = numpy.var(z[lower_lim:upper_lim])
					z_rms = numpy.sqrt(numpy.mean(numpy.square(z[lower_lim:upper_lim])))
					z_IQR = numpy.subtract(*numpy.percentile(z[lower_lim:upper_lim], [75, 25]))
					#Mean x Rate
					zArray = numpy.array(z[lower_lim:upper_lim])
					zArray = zArray - z_mean
					z_meanXrate = (numpy.diff(numpy.sign(zArray)) != 0).sum()*2.7 #ZeroCrossingRate = when x[-1]*x[0] changes sign
					z_meanDiff = numpy.mean(numpy.diff(z[lower_lim:upper_lim]))
					z_maxDiff = max(numpy.diff(z[lower_lim:upper_lim]))*1.5

					##### mag features #####
					mag_max = max(mag[lower_lim:upper_lim])
					mag_mean = numpy.mean(mag[lower_lim:upper_lim])
					mag_median = numpy.median(mag[lower_lim:upper_lim])
					mag_var = numpy.var(mag[lower_lim:upper_lim])
					mag_rms = numpy.sqrt(numpy.mean(numpy.square(mag[lower_lim:upper_lim])))
					mag_IQR = numpy.subtract(*numpy.percentile(mag[lower_lim:upper_lim], [75, 25]))
					#Mean x Rate
					magArray = numpy.array(mag[lower_lim:upper_lim])
					magArray = magArray - mag_mean
					mag_meanXrate = (numpy.diff(numpy.sign(magArray)) != 0).sum()*2.3 #ZeroCrossingRate = when x[-1]*x[0] changes sign
					mag_meanDiff = numpy.mean(numpy.diff(mag[lower_lim:upper_lim]))
					mag_maxDiff = max(numpy.diff(mag[lower_lim:upper_lim]))*1.5

					#corrcoef
					corr_xy = numpy.corrcoef(x[lower_lim:upper_lim],y[lower_lim:upper_lim])[0,1]
					corr_xz = numpy.corrcoef(z[lower_lim:upper_lim],x[lower_lim:upper_lim])[0,1]
					corr_yz = numpy.corrcoef(y[lower_lim:upper_lim],z[lower_lim:upper_lim])[0,1]

					with open(PebbleFeatureFileName, "a") as PebbleFeatureFile:
						PebbleFeatureFile.write(str(timestamp_1) + ", " + str(timestamp_2) 
							+ ", " + str(x_mean) + ", " + str(x_median) + ", " + str(x_max) 
							+ ", " + str(x_var) + ", " + str(x_rms) + ", " + str(x_IQR) 
							+ ", " + str(x_meanXrate) + ", " + str(x_meanDiff) + ", " + str(x_maxDiff)  
							+ ", " + str(x_teager_mean) + ", " + str(x_teager_std) + ", " + str(x_teager_max)
							+ ", " + str(x_fft_mean_0_1) + ", " + str(x_fft_0_1_max) + ", " + str(x_fft_mean_1_3)
							+ ", " + str(x_fft_1_3_max) + ", " + str(x_fft_mean_3_10) + ", " + str(x_fft_3_10_max)  
							+ ", " + str(y_mean) + ", " + str(y_median) + ", " + str(y_max) 
							+ ", " + str(y_var) + ", " + str(y_rms) + ", " + str(y_IQR) 
							+ ", " + str(y_meanXrate) + ", " + str(y_meanDiff) + ", " + str(y_maxDiff)  
							+ ", " + str(y_teager_mean) + ", " + str(y_teager_std) + ", " + str(y_teager_max)
							+ ", " + str(y_fft_mean_0_1) + ", " + str(y_fft_0_1_max) + ", " + str(y_fft_mean_1_3)
							+ ", " + str(y_fft_1_3_max) + ", " + str(y_fft_mean_3_10) + ", " + str(y_fft_3_10_max) 
							+ ", " + str(z_mean) + ", " + str(z_median) + ", " + str(z_max) 
							+ ", " + str(z_var) + ", " + str(z_rms) + ", " + str(z_IQR) 
							+ ", " + str(z_meanXrate) + ", " + str(z_meanDiff) + ", " + str(z_maxDiff)  
							+ ", " + str(z_teager_mean) + ", " + str(z_teager_std) + ", " + str(z_teager_max)
							+ ", " + str(z_fft_mean_0_1) + ", " + str(z_fft_0_1_max) + ", " + str(z_fft_mean_1_3)
							+ ", " + str(z_fft_1_3_max) + ", " + str(z_fft_mean_3_10) + ", " + str(z_fft_3_10_max) 
							+ ", " + str(mag_mean) + ", " + str(mag_median) + ", " + str(mag_max) 
							+ ", " + str(mag_var) + ", " + str(mag_rms) + ", " + str(mag_IQR) 
							+ ", " + str(mag_meanXrate) + ", " + str(mag_meanDiff) + ", " + str(mag_maxDiff)  
							+ ", " + str(mag_teager_mean) + ", " + str(mag_teager_std) + ", " + str(mag_teager_max)
							+ ", " + str(mag_fft_mean_0_1) + ", " + str(mag_fft_0_1_max) + ", " + str(mag_fft_mean_1_3)
							+ ", " + str(mag_fft_1_3_max) + ", " + str(mag_fft_mean_3_10) + ", " + str(mag_fft_3_10_max) 
							+ ", " + str(corr_xy) + ", " + str(corr_xz) + ", " + str(corr_yz)
							+ "\n ")
					# with open(PebbleFeatureFileName, "a") as PebbleFeatureFile:
					# 	PebbleFeatureFile.write(str(timestamp_1) + ", " + str(timestamp_2) 
					# 		+ ", " + str(x_mean) + ", " + str(x_median) + ", " + str(x_max) 
					# 		+ ", " + str(x_var) + ", " + str(x_rms) + ", " + str(x_IQR) 
					# 		+ ", " + str(x_meanXrate) + ", " + str(x_meanDiff) + ", " + str(x_maxDiff)  
					# 		+ ", " + str(x_teager_mean) + ", " + str(x_teager_std) + ", " + str(x_teager_max)
					# 		+ ", " + str(x_fft_0_1_max) + ", " + str(x_fft_mean_0_1) + ", " + str(x_fft_1_3_max)
					# 		+ ", " + str(x_fft_mean_1_3) + ", " + str(x_fft_3_10_max) + ", " + str(x_fft_mean_3_10)  
					# 		+ ", " + str(y_mean) + ", " + str(y_median) + ", " + str(y_max) 
					# 		+ ", " + str(y_var) + ", " + str(y_rms) + ", " + str(y_IQR) 
					# 		+ ", " + str(y_meanXrate) + ", " + str(y_meanDiff) + ", " + str(y_maxDiff)  
					# 		+ ", " + str(y_teager_mean) + ", " + str(y_teager_std) + ", " + str(y_teager_max)
					# 		+ ", " + str(y_fft_0_1_max) + ", " + str(y_fft_mean_0_1) + ", " + str(y_fft_1_3_max)
					# 		+ ", " + str(y_fft_mean_1_3) + ", " + str(y_fft_3_10_max) + ", " + str(y_fft_mean_3_10) 
					# 		+ ", " + str(z_mean) + ", " + str(z_median) + ", " + str(z_max) 
					# 		+ ", " + str(z_var) + ", " + str(z_rms) + ", " + str(z_IQR) 
					# 		+ ", " + str(z_meanXrate) + ", " + str(z_meanDiff) + ", " + str(z_maxDiff)  
					# 		+ ", " + str(z_teager_mean) + ", " + str(z_teager_std) + ", " + str(z_teager_max)
					# 		+ ", " + str(z_fft_0_1_max) + ", " + str(z_fft_mean_0_1) + ", " + str(z_fft_1_3_max)
					# 		+ ", " + str(z_fft_mean_1_3) + ", " + str(z_fft_3_10_max) + ", " + str(z_fft_mean_3_10) 
					# 		+ ", " + str(mag_mean) + ", " + str(mag_median) + ", " + str(mag_max) 
					# 		+ ", " + str(mag_var) + ", " + str(mag_rms) + ", " + str(mag_IQR) 
					# 		+ ", " + str(mag_meanXrate) + ", " + str(mag_meanDiff) + ", " + str(mag_maxDiff)  
					# 		+ ", " + str(mag_teager_mean) + ", " + str(mag_teager_std) + ", " + str(mag_teager_max)
					# 		+ ", " + str(mag_fft_0_1_max) + ", " + str(mag_fft_mean_0_1) + ", " + str(mag_fft_1_3_max)
					# 		+ ", " + str(mag_fft_mean_1_3) + ", " + str(mag_fft_3_10_max) + ", " + str(mag_fft_mean_3_10)
					# 		+ ", " + str(corr_xy) + ", " + str(corr_xz) + ", " + str(corr_yz)
					# 		+ "\n ")
					#construct Features Message to send to base station
					featureMessage = (str(timestamp_1) + ", " + str(timestamp_2) 
						+ ", " + str(x_mean) + ", " + str(x_median) + ", " + str(x_max) 
						+ ", " + str(x_var) + ", " + str(x_rms) + ", " + str(x_IQR) 
						+ ", " + str(x_meanXrate) + ", " + str(x_meanDiff) + ", " + str(x_maxDiff)  
						+ ", " + str(x_teager_mean) + ", " + str(x_teager_std) + ", " + str(x_teager_max)
						+ ", " + str(x_fft_mean_0_1) + ", " + str(x_fft_0_1_max) + ", " + str(x_fft_mean_1_3)
						+ ", " + str(x_fft_1_3_max) + ", " + str(x_fft_mean_3_10) + ", " + str(x_fft_3_10_max)  
						+ ", " + str(y_mean) + ", " + str(y_median) + ", " + str(y_max) 
						+ ", " + str(y_var) + ", " + str(y_rms) + ", " + str(y_IQR) 
						+ ", " + str(y_meanXrate) + ", " + str(y_meanDiff) + ", " + str(y_maxDiff)  
						+ ", " + str(y_teager_mean) + ", " + str(y_teager_std) + ", " + str(y_teager_max)
						+ ", " + str(y_fft_mean_0_1) + ", " + str(y_fft_0_1_max) + ", " + str(y_fft_mean_1_3)
						+ ", " + str(y_fft_1_3_max) + ", " + str(y_fft_mean_3_10) + ", " + str(y_fft_3_10_max) 
						+ ", " + str(z_mean) + ", " + str(z_median) + ", " + str(z_max) 
						+ ", " + str(z_var) + ", " + str(z_rms) + ", " + str(z_IQR) 
						+ ", " + str(z_meanXrate) + ", " + str(z_meanDiff) + ", " + str(z_maxDiff)  
						+ ", " + str(z_teager_mean) + ", " + str(z_teager_std) + ", " + str(z_teager_max)
						+ ", " + str(z_fft_mean_0_1) + ", " + str(z_fft_0_1_max) + ", " + str(z_fft_mean_1_3)
						+ ", " + str(z_fft_1_3_max) + ", " + str(z_fft_mean_3_10) + ", " + str(z_fft_3_10_max) 
						+ ", " + str(mag_mean) + ", " + str(mag_median) + ", " + str(mag_max) 
						+ ", " + str(mag_var) + ", " + str(mag_rms) + ", " + str(mag_IQR) 
						+ ", " + str(mag_meanXrate) + ", " + str(mag_meanDiff) + ", " + str(mag_maxDiff)  
						+ ", " + str(mag_teager_mean) + ", " + str(mag_teager_std) + ", " + str(mag_teager_max)
						+ ", " + str(mag_fft_mean_0_1) + ", " + str(mag_fft_0_1_max) + ", " + str(mag_fft_mean_1_3)
						+ ", " + str(mag_fft_1_3_max) + ", " + str(mag_fft_mean_3_10) + ", " + str(mag_fft_3_10_max) 
						+ ", " + str(corr_xy) + ", " + str(corr_xz) + ", " + str(corr_yz)
						+ "")
					PORT = 9000 
					server_address = (hostIP, PORT)
					testFeatureSending.sendFeature(server_address, featureMessage, 5)

					# timestamp_1,timestamp_2,

					# x_max,x_min,x_mean,x_std,x_fft_mean,x_fft_0_1_max,x_fft_mean_0_1,x_fft_1_3_max,
					# x_fft_mean_1_3,x_fft_3_10_max,x_fft_mean_3_10,x_teager_mean,x_teager_max,

					# y_max,y_min,y_mean,y_std,y_fft_mean,y_fft_0_1_max,y_fft_mean_0_1,y_fft_1_3_max,
					# y_fft_mean_1_3,y_fft_3_10_max,y_fft_mean_3_10,y_teager_mean,y_teager_max,

					# z_max,z_min,z_mean,z_std,z_fft_mean,z_fft_0_1_max,z_fft_mean_0_1,z_fft_1_3_max,
					# z_fft_mean_1_3,z_fft_3_10_max,z_fft_mean_3_10,z_teager_mean,z_teager_max

					#move the data according to Step Size (1500 samples)
					del rawX[0:stepSize]
					del rawY[0:stepSize]
					del rawZ[0:stepSize]
					del rawTime[0:stepSize]
					
					HB_Pixie_Value = x_max

				else: #the buffer is not exceed 3000 sample yet
					time.sleep(5)

				# iterations += 1
				# if iterations>=4: # heart beat
				#       iterations = 0
				#       pixieMessage = []
				#       pixieMessage.append("Pixie")
				#       pixieMessage.append(str("{0:.3f}".format(HB_Pixie_Value))) #HB_Pixie_Value = x_max
				#       tempDateTime = rNTPTime.sendUpdate(server_address, pixieMessage, 5)

						
# do stuff in main() -- for 'after declare' function
if __name__ == '__main__':
    main()



