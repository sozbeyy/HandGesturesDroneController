import matplotlib
matplotlib.use("TkAgg")
from utils import detector_utils as detector_utils
import tkinter as tk
from tkinter import *
from ScrolledText import ScrolledText
import cv2
import tensorflow as tf
import threading
import datetime
import argparse
from matplotlib import pyplot as plt
from PIL import Image
from PIL import ImageTk
import matplotlib.animation as animation
import numpy as np
import Queue



detection_graph, sess = detector_utils.load_inference_graph()
class hand_gesture_detector:

	def __init__(self,video_streaming_obj):
		self.video_streaming_obj = video_streaming_obj
		self.frame = None
		self.thread = None
		self.stopEvent = threading.Event()

		# max number of hands we want to detect/track
		self.num_hands_detect = 2

		#initialize the root window and image panel
		self.root = Tk()
		self.panel = None
		self.scrolled_text= ScrolledText(self.root, wrap=tk.WORD,width=40,bg='black')
		self.scrolled_text.pack(side=RIGHT, fill=Y, expand=1)
		self.scrolled_text.tag_config('normal', foreground='white')
		self.scrolled_text.tag_config('telemetry', foreground='red')
		
		self.scrolled_text.yview(tk.END)

		self.thread = threading.Thread(target=self.videoLoop, args=())
		self.thread.start()

		# set a callback to handle when the window is closed
		self.root.wm_title("Hand Gestures Detector")
		self.root.wm_protocol("WM_DELETE_WINDOW", self.onClose)

		# Detection parameters

		self.prev_first_sample_points_xy = [(0,0),(0,0),(0,0),(0,0),(0,0)]
		self.first_sample_points_xy = [(0,0),(0,0),(0,0),(0,0),(0,0)]

		self.prev_second_sample_points_xy = [(0,0),(0,0),(0,0),(0,0),(0,0)]
		self.second_sample_points_xy = [(0,0),(0,0),(0,0),(0,0),(0,0)]

		im_width, im_height = (int(self.video_streaming_obj.get(3)), int(self.video_streaming_obj.get(4)))
		self.start_x = int(im_width)
		self.start_y = int(im_height)

		self.prev_first_hand_shape = -1
		self.prev_second_hand_shape = -1   

		self.prev_box_1 = None
		self.prev_box_2 = None

		self.box_1 = None
		self.box_2 = None

		self.first_hand_shape = -1
		self.second_hand_shape = -1

		self.gestures_queue_first = Queue.Queue()
		self.gestures_queue_second = Queue.Queue()

		self.is_connected = False
		self.connect_pattern = [1, 0, 1]
		self.score_thresh = 0.7

		self.output_img = np.zeros((700,1200,3),dtype= np.uint8)


		self.num_of_frames_without_hands = 0
		self.num_of_frames_before_flip_hand_boxes = 0
		self.bg_frame = None

		self.lock_wheel = False
		self.num_of_frames_lock_wheel=0

		self.arrow_shift = 0;

		#Control Mode
		control_mode = {}
		control_mode['OFF']=0
		control_mode['ARMED']=0
		control_mode['TAKEOFF']=0
		control_mode['FLYING_WHEEL']=0
		control_mode['FLYTING_RIGHT']=0
		control_mode['FLYTING_LEFT']=0
		

		#initialize queues
		for i in range(3):
			self.gestures_queue_first.put(-1)
			self.gestures_queue_second.put(-1)

	def onClose(self):
		# set the stop event, cleanup the camera, and allow the rest of
		# the quit process to continue
		print("[INFO] closing...")
		self.stopEvent.set()
		self.video_streaming_obj.release()
		self.root.quit()

	def videoLoop(self):
		im_width, im_height = (int(self.video_streaming_obj.get(3)), int(self.video_streaming_obj.get(4)))

		
		try:
			while not self.stopEvent.is_set():
				_, image_np = self.video_streaming_obj.read()
				# image_np = cv2.flip(image_np, 1)
				try:
					image_np = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
				except:
					print("Error converting to RGB")

				boxes, scores, classes = detector_utils.detect_objects(
					image_np, detection_graph, sess)
				image = cv2.cvtColor(self.output_img,cv2.COLOR_BGR2RGB)
				image = Image.fromarray(image)
				image = ImageTk.PhotoImage(image)

				if self.panel is None:
					self.panel = Label(image=image)
					self.panel.image = image
					self.panel.pack(side="left", padx=2, pady=2)
					# self.scrolled_text.insert(tk.INSERT,"N")
					

					
				else:
					self.panel.configure(image=image)
					self.panel.image = image
					self.scrolled_text.insert(END, "message to be sent \n", 'normal')
					self.scrolled_text.insert(END, "incoming message \n", 'telemetry')
					

				#filter by score
				tmp_scores = []
				tmp_classes = []
				tmp_boxes = []

				for i in range(self.num_hands_detect):
				   if (scores[i] > self.score_thresh):
					   tmp_scores.append(scores[i])
					   tmp_classes.append(classes[i])
					   tmp_boxes.append(boxes[i])

				#filter by score
				filtered_scores = [];
				filtered_classes = [];
				filtered_boxes = [];
				# image_np=detector_utils.draw_left_arrow(image_np);
				for i in range(len(tmp_scores)):
					redundant = False;
					(left_1, right_1, top_1, bottom_1) = (tmp_boxes[i][1] * im_width, tmp_boxes[i][3] * im_width,
													  tmp_boxes[i][0] * im_height, tmp_boxes[i][2] * im_height)
					area_1 = (right_1-left_1)*(bottom_1-top_1)
					for j in range(i+1,len(tmp_scores)):
						(left_2, right_2, top_2, bottom_2) = (tmp_boxes[j][1] * im_width, tmp_boxes[j][3] * im_width,
													  tmp_boxes[j][0] * im_height, tmp_boxes[j][2] * im_height)
						area_2 = (right_2-left_2)*(bottom_2-top_2)
						x = max(left_1, left_2)
						y = max(top_1, top_2)
						w = min(right_1, right_2) - x
						h = min(bottom_1, bottom_2) - y
						if w<0 or h<0:
							continue;
						else:
							print 'There is intersection'
							if w*h> 0.8*area_1:
								print 'redundant'
								redundant = True;
								break;
					if not redundant:
						filtered_scores.append(tmp_scores[i])
						filtered_classes.append(tmp_classes[i])
						filtered_boxes.append(tmp_boxes[i])

				accepted_hands_count = 0;
				# if len(filtered_scores)==0:
				# 	self.num_of_frames_without_hands+=1

				# if self.num_of_frames_without_hands >4:
				# 	print 'New BG, No hands detected!'
				# 	self.bg_frame = image_np

				if self.arrow_shift>3:
					self.arrow_shift = 0
				else:
					self.arrow_shift+=1

				# Lock wheel for 3 frames in case of noise 
				if self.lock_wheel and self.num_of_frames_lock_wheel<3:
					if len(filtered_scores)==2 and ((filtered_classes[0]==6.0 and not filtered_classes[1]==6.0) or (not filtered_classes[0]==6.0 and filtered_classes[1]==6.0)):
						print 'LOCK 2 HAND...'
						self.num_of_frames_lock_wheel+=1
						if self.num_of_frames_lock_wheel>=3:
							self.lock_wheel = False
							self.num_of_frames_lock_wheel=0
						image_np = detector_utils.draw_steering_wheel(image_np,self.first_sample_points_xy[0][1]-self.second_sample_points_xy[0][1])
						# if self.first_sample_points_xy[0][0]>self.second_sample_points_xy[0][0]:
						# 	image_np = detector_utils.draw_steering_wheel(image_np,self.first_sample_points_xy[0][1]-self.second_sample_points_xy[0][1])
						# else:
						# 	image_np = detector_utils.draw_steering_wheel(image_np,self.second_sample_points_xy[0][1]-self.first_sample_points_xy[0][1])
					elif len(filtered_scores)==1 and filtered_classes[0]==6.0:
							image_np = detector_utils.draw_steering_wheel(image_np,0)
							print 'LOCK 1 HAND...'
							self.num_of_frames_lock_wheel+=1
							if self.num_of_frames_lock_wheel>=3:
								self.lock_wheel = False
								self.num_of_frames_lock_wheel=0




				if len(filtered_scores)==1:
					(left_1, right_1, top_1, bottom_1) = (filtered_boxes[0][1] * im_width, filtered_boxes[0][3] * im_width,
											filtered_boxes[0][0] * im_height, filtered_boxes[0][2] * im_height)

					width_1 = right_1 - left_1
					height_1 = bottom_1 - top_1

					self.prev_box_1 = self.box_1
					self.box_1 = filtered_boxes[0]
					self.prev_first_hand_shape = self.first_hand_shape
					self.first_hand_shape = filtered_classes[0];

					self.prev_first_sample_points_xy = self.first_sample_points_xy
					self.first_sample_points_xy = [(int(left_1+width_1/4),int(top_1+height_1/4)),
											(int(right_1-width_1/4),int(top_1+height_1/4)),
											(int(left_1+width_1/4),int(bottom_1-height_1/4)),
											(int(right_1-width_1/4),int(bottom_1-height_1/4)),
											(int(right_1-width_1/2),int(bottom_1-height_1/2))]

					cv2.rectangle(image_np, (int(left_1),int(top_1)), (int(right_1),int(bottom_1)), (0, 0, 255), 1)
					cv2.putText(image_np, 'BOX',(int(right_1)-15, int(top_1)-5),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,0))
					cv2.putText(image_np,str(filtered_classes[0]),(int(left_1)-5, int(top_1)-5),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0))
					for k in range(5):
						cv2.circle(image_np,self.first_sample_points_xy[k], 2, (0,0,255), -1)
						cv2.line(image_np,self.prev_first_sample_points_xy[k],self.first_sample_points_xy[k],(255,0,0),1)

					self.prev_box_2 = None
					self.box_2 = None
					self.prev_second_hand_shape = None
					self.second_hand_shape = None

					# self.prev_second_sample_points_xy = [(0,0),(0,0),(0,0),(0,0),(0,0)]
					# self.second_sample_points_xy = [(0,0),(0,0),(0,0),(0,0),(0,0)]
					
				elif len(filtered_scores)==2:
					(left_1, right_1, top_1, bottom_1) = (filtered_boxes[0][1] * im_width, filtered_boxes[0][3] * im_width,
											filtered_boxes[0][0] * im_height, filtered_boxes[0][2] * im_height)

					width_1 = right_1 - left_1
					height_1 = bottom_1 - top_1

					(left_2, right_2, top_2, bottom_2) = (filtered_boxes[1][1] * im_width, filtered_boxes[1][3] * im_width,
											filtered_boxes[1][0] * im_height, filtered_boxes[1][2] * im_height)

					width_2 = right_2 - left_2
					height_2 = bottom_2 - top_2

					coordinates = [[left_1, right_1, top_1, bottom_1,width_1,height_1],[left_2, right_2, top_2, bottom_2,width_2,height_2]]

					left_box_index = 0
					rigth_box_index = 1
					if left_1>left_2:
						left_box_index = 1
						rigth_box_index = 0
					self.prev_box_1 = self.box_1
					self.box_1 = filtered_boxes[left_box_index]
					self.prev_first_hand_shape = self.first_hand_shape
					self.first_hand_shape = filtered_classes[left_box_index];

					self.prev_first_sample_points_xy = self.first_sample_points_xy
											# [(int(left_1+width_1/4),int(top_1+height_1/4)),
											#  (int(right_1-width_1/4),int(top_1+height_1/4)),
											#  (int(left_1+width_1/4),int(bottom_1-height_1/4)),
											#  (int(right_1-width_1/4),int(bottom_1-height_1/4)),
											#  (int(right_1-width_1/2),int(bottom_1-height_1/2))]
					self.first_sample_points_xy = [(int(coordinates[left_box_index][0]+coordinates[left_box_index][4]/4),int(coordinates[left_box_index][2]+coordinates[left_box_index][5]/4)),
													(int(coordinates[left_box_index][1]-coordinates[left_box_index][4]/4),int(coordinates[left_box_index][2]+coordinates[left_box_index][5]/4)),
													(int(coordinates[left_box_index][0]+coordinates[left_box_index][4]/4),int(coordinates[left_box_index][3]-coordinates[left_box_index][5]/4)),
													(int(coordinates[left_box_index][1]-coordinates[left_box_index][4]/4),int(coordinates[left_box_index][3]-coordinates[left_box_index][5]/4)),
													(int(coordinates[left_box_index][1]-coordinates[left_box_index][4]/2),int(coordinates[left_box_index][3]-coordinates[left_box_index][5]/2))]

					cv2.rectangle(image_np, (int(coordinates[left_box_index][0]),int(coordinates[left_box_index][2])), (int(coordinates[left_box_index][1]),int(coordinates[left_box_index][3])), (0, 0, 255), 1)
					cv2.putText(image_np, 'BOX1',(int(coordinates[left_box_index][1])-20, int(coordinates[left_box_index][2])-5),cv2.FONT_HERSHEY_SIMPLEX,0.4,(0,255,0))
					cv2.putText(image_np,str(filtered_classes[left_box_index]),(int(coordinates[left_box_index][0])-5, int(coordinates[left_box_index][2])-5),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0))

					self.prev_box_2 = self.box_2
					self.box_2 = filtered_boxes[rigth_box_index]
					self.prev_second_hand_shape = self.second_hand_shape
					self.second_hand_shape = filtered_classes[rigth_box_index];

					self.prev_second_sample_points_xy = self.second_sample_points_xy
					self.second_sample_points_xy = [(int(coordinates[rigth_box_index][0]+coordinates[rigth_box_index][4]/4),int(coordinates[rigth_box_index][2]+coordinates[rigth_box_index][5]/4)),
													(int(coordinates[rigth_box_index][1]-coordinates[rigth_box_index][4]/4),int(coordinates[rigth_box_index][2]+coordinates[rigth_box_index][5]/4)),
													(int(coordinates[rigth_box_index][0]+coordinates[rigth_box_index][4]/4),int(coordinates[rigth_box_index][3]-coordinates[rigth_box_index][5]/4)),
													(int(coordinates[rigth_box_index][1]-coordinates[rigth_box_index][4]/4),int(coordinates[rigth_box_index][3]-coordinates[rigth_box_index][5]/4)),
													(int(coordinates[rigth_box_index][1]-coordinates[rigth_box_index][4]/2),int(coordinates[rigth_box_index][3]-coordinates[rigth_box_index][5]/2))]

					cv2.rectangle(image_np, (int(coordinates[rigth_box_index][0]),int(coordinates[rigth_box_index][2])), (int(coordinates[rigth_box_index][1]),int(coordinates[rigth_box_index][3])), (255, 0, 0), 1)
					cv2.putText(image_np, 'BOX2',(int(coordinates[rigth_box_index][1])-20, int(coordinates[rigth_box_index][2])-5),cv2.FONT_HERSHEY_SIMPLEX,0.4,(255,0,0))
					cv2.putText(image_np,str(filtered_classes[rigth_box_index]),(int(coordinates[rigth_box_index][0])-5, int(coordinates[rigth_box_index][2])-5),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0))

					#show Wheel when shapes: close close
					if  not detector_utils.is_hand_opened(self.first_hand_shape) and not detector_utils.is_hand_opened(self.second_hand_shape):
						self.lock_wheel = True
						self.num_of_frames_lock_wheel=0
						image_np = detector_utils.draw_steering_wheel(image_np,self.first_sample_points_xy[0][1]-self.second_sample_points_xy[0][1])
						# if self.first_sample_points_xy[0][0]>self.second_sample_points_xy[0][0]:
						# 	image_np = detector_utils.draw_steering_wheel(image_np,self.first_sample_points_xy[0][1]-self.second_sample_points_xy[0][1])
						# else:
						# 	image_np = detector_utils.draw_steering_wheel(image_np,self.second_sample_points_xy[0][1]-self.first_sample_points_xy[0][1])

					#show arrow when shapes: open close
					if detector_utils.is_hand_opened(self.first_hand_shape) and not detector_utils.is_hand_opened(self.second_hand_shape):
						self.lock_wheel = False
						image_np = detector_utils.draw_right_arrow(image_np,self.arrow_shift)
					elif not detector_utils.is_hand_opened(self.first_hand_shape) and  detector_utils.is_hand_opened(self.second_hand_shape):
						self.lock_wheel = False
						image_np = detector_utils.draw_left_arrow(image_np,self.arrow_shift)


					#show sample points for each detected hand
					for k in range(5):
						cv2.circle(image_np,self.first_sample_points_xy[k], 2, (0,0,255), -1)
						cv2.line(image_np,self.prev_first_sample_points_xy[k],self.first_sample_points_xy[k],(255,0,0),1)

						cv2.circle(image_np,self.second_sample_points_xy[k], 2, (0,0,255), -1)
						cv2.line(image_np,self.prev_second_sample_points_xy[k],self.second_sample_points_xy[k],(255,0,0),1)
				else:
					print 'No HANDS *_*', len(filtered_boxes)
				

				'''
				if len(filtered_scores)>1 and not self.prev_box_1 is None and not self.prev_box_2 is None:
					(left_1, right_1, top_1, bottom_1) = (filtered_boxes[0][1] * im_width, filtered_boxes[0][3] * im_width,
											filtered_boxes[0][0] * im_height, filtered_boxes[0][2] * im_height)

					width_1 = right_1 - left_1
					height_1 = bottom_1 - top_1

					(left_2, right_2, top_2, bottom_2) = (filtered_boxes[1][1] * im_width, filtered_boxes[1][3] * im_width,
											filtered_boxes[1][0] * im_height, filtered_boxes[1][2] * im_height)

					width_2 = right_2 - left_2
					height_2 = bottom_2 - top_2

					

					x1,y1,w_1,h_1,right_1, right_2,left_1,left_2 = detector_utils.calculate_intersection(filtered_boxes[0],self.prev_box_1,im_width,im_height)
					x2,y2,w_2,h_2,right_12, right_22,left_12,left_22 = detector_utils.calculate_intersection(filtered_boxes[0],self.prev_box_2,im_width,im_height)
					if w_1*h_1>=w_2*h_2:
						self.prev_box_1 = self.box_1
						self.box_1 = filtered_boxes[0]
						self.prev_first_hand_shape = self.first_hand_shape
						self.first_hand_shape = filtered_classes[0];

						self.prev_first_sample_points_xy = self.first_sample_points_xy
						self.first_sample_points_xy = [(int(left_1+width_1/4),int(top_1+height_1/4)),
											 (int(right_1-width_1/4),int(top_1+height_1/4)),
											 (int(left_1+width_1/4),int(bottom_1-height_1/4)),
											 (int(right_1-width_1/4),int(bottom_1-height_1/4)),
											 (int(right_1-width_1/2),int(bottom_1-height_1/2))]

						self.prev_box_2 = self.box_2
						self.box_2 = filtered_boxes[1]
						self.prev_second_hand_shape = self.second_hand_shape
						self.second_hand_shape = filtered_classes[1];

						self.prev_second_sample_points_xy = self.second_sample_points_xy
						self.second_sample_points_xy = [(int(left_2+width_2/4),int(top_2+height_2/4)),
											 (int(right_2-width_2/4),int(top_2+height_2/4)),
											 (int(left_2+width_2/4),int(bottom_2-height_2/4)),
											 (int(right_2-width_2/4),int(bottom_2-height_2/4)),
											 (int(right_2-width_2/2),int(bottom_2-height_2/2))]


					else:
						self.prev_box_1 = self.box_1
						self.box_1 = filtered_boxes[1]
						self.prev_first_hand_shape = self.first_hand_shape
						self.first_hand_shape = filtered_classes[1];

						self.prev_first_sample_points_xy = self.first_sample_points_xy
						self.first_sample_points_xy = [(int(left_2+width_2/4),int(top_2+height_2/4)),
											 (int(right_2-width_2/4),int(top_2+height_2/4)),
											 (int(left_2+width_2/4),int(bottom_2-height_2/4)),
											 (int(right_2-width_2/4),int(bottom_2-height_2/4)),
											 (int(right_2-width_2/2),int(bottom_2-height_2/2))]

					for k in range(5):
							cv2.circle(image_np,self.first_sample_points_xy[k], 2, (0,0,255), -1)
							cv2.line(image_np,self.prev_first_sample_points_xy[k],self.first_sample_points_xy[k],(255,0,0),1)

							cv2.circle(image_np,self.second_sample_points_xy[k], 2, (0,0,255), -1)
							cv2.line(image_np,self.prev_second_sample_points_xy[k],self.second_sample_points_xy[k],(255,0,0),1)

					

				elif  len(filtered_scores)==1 and self.prev_box_1 is None and not self.box_1 is None:
					print 'initial'
					self.prev_box_1 = self.box_1
				elif len(filtered_scores)==1 and self.prev_box_1 is None and  self.box_1 is None:
					self.box_1 = filtered_boxes[0]
				elif len(filtered_scores)==1 and self.box_1 is None and self.box_2 is None:
					print 'BOTH None'
					self.box_1 = filtered_boxes[0]
				elif len(filtered_scores)==2:
					self.prev_second_hand_shape = self.second_hand_shape
					self.second_hand_shape = filtered_classes[i];

					self.prev_box_2 = self.box_2;
					self.box_2 = filtered_boxes[i]
				else:
					print 'Unsolved :D'
				'''





				'''
				for i in range(len(filtered_scores)):
				# 	self.num_of_frames_without_hands = 0
					
					accepted_hands_count+=1;

					if accepted_hands_count>2:
						break;

					
					(left, right, top, bottom) = (filtered_boxes[i][1] * im_width, filtered_boxes[i][3] * im_width,
												  filtered_boxes[i][0] * im_height, filtered_boxes[i][2] * im_height)
					p1 = (int(left), int(top))
					p2 = (int(right), int(bottom))

					width = right - left;
					height = bottom - top;





						


					

					if accepted_hands_count == 1:	
						self.prev_second_hand_shape = self.second_hand_shape
						self.second_hand_shape = -1;

						self.first_sample_points_xy = [(int(left+width/4),int(top+height/4)),
											 (int(right-width/4),int(top+height/4)),
											 (int(left+width/4),int(bottom-height/4)),
											 (int(right-width/4),int(bottom-height/4)),
											 (int(right-width/2),int(bottom-height/2))]

						for k in range(5):
							cv2.circle(image_np,self.first_sample_points_xy[k], 2, (0,0,255), -1)
							cv2.line(image_np,self.prev_first_sample_points_xy[k],self.first_sample_points_xy[k],(255,0,0),1)

						self.prev_first_sample_points_xy = self.first_sample_points_xy

						if self.prev_box_1 is None and not self.box_1 is None:
							print 'initial'
							self.prev_box_1 = self.box_1

						if self.box_1 is None and self.box_2 is None:
							print 'BOTH None'
							self.box_1 = filtered_boxes[i]

						if self.box_1 is None and not self.box_2 is None:
							print '1st None, 2nd NOT None'
							self.box_1 = self.box_2
							self.prev_box_1 = self.prev_box_2
							self.prev_first_hand_shape = self.second_hand_shape
							self.first_hand_shape = filtered_classes[i];
							self.prev_second_hand_shape = -1
							self.second_hand_shape = -1;
							self.box_2 = None
							self.prev_box_2 = None



						if not self.prev_box_1 is None and not self.prev_box_2 is None:
							print 'BOTH NOT None'
							x1,y1,w_1,h_1,right_1, right_2,left_1,left_2 = detector_utils.calculate_intersection(filtered_boxes[i],self.prev_box_1,im_width,im_height)
							x2,y2,w_2,h_2,right_12, right_22,left_12,left_22 = detector_utils.calculate_intersection(filtered_boxes[i],self.prev_box_2,im_width,im_height)

							# if w_1*h_1 >= w_2*h_2:
							width = 
							if len(filtered_classes)>1:
								(left_1, right_1, top_1, bottom_1) = (filtered_classes[0][1] * im_width, filtered_classes[0][3] * im_width,
                                              filtered_classes[0][0] * im_height, filtered_classes[0][2] * im_height)
								(left_2, right_2, _, _) = (filtered_classes[1][1] * im_width, filtered_classes[1][3] * im_width,
                                              filtered_classes[1][0] * im_height, filtered_classes[1][2] * im_height)
								if 
							self.prev_box_1 = self.box_1
							self.box_1 = filtered_boxes[i]
							self.prev_first_hand_shape = self.first_hand_shape
							self.first_hand_shape = filtered_classes[i];
							print len(filtered_classes)
							# else:
								# if self.num_of_frames_before_flip_hand_boxes>=3:
									# print filtered_boxes[i],self.prev_box_1,self.prev_box_2
								# print 'change', x1,y1,w_1,h_1,right_1, right_2,left_1,left_2,' ',x2,y2,w_2,h_2,right_12, right_22,left_12,left_22
								# self.num_of_frames_before_flip_hand_boxes=0;
								# #change previous boxes - first <-> second
								# tmp_box = self.prev_box_1
								# self.prev_box_1 = self.prev_box_2
								# self.prev_box_2 = tmp_box

								# tmp_hand_shape = self.prev_first_hand_shape
								# self.prev_first_hand_shape = self.prev_second_hand_shape
								# self.prev_second_hand_shape = tmp_hand_shape


								# self.prev_first_hand_shape = self.second_hand_shape
								# self.second_hand_shape = self.first_hand_shape

								# self.first_hand_shape = filtered_classes[i];

								# self.prev_box_1 = self.box_1
								# self.box_1 = filtered_boxes[i]

								# tmp_queue = Queue.Queue()
								# tmp_queue = self.gestures_queue_first;
								# self.gestures_queue_first = self.gestures_queue_second
								# self.gestures_queue_second = tmp_queue

								# tmp_sample = self.first_sample_points_xy
								# self.first_sample_points_xy = self.second_sample_points_xy
								# self.second_sample_points_xy = tmp_sample

								# prev_tmp_sample = self.prev_first_sample_points_xy
								# self.prev_first_sample_points_xy = self.prev_second_sample_points_xy
								# self.prev_second_sample_points_xy = prev_tmp_sample

								# else:
								# 	print 'num_of_frames_before_flip_hand_boxes: ',self.num_of_frames_before_flip_hand_boxes
								# 	self.num_of_frames_before_flip_hand_boxes += 1;

						elif not self.prev_box_1 is None and self.prev_box_2 is None:
							self.prev_box_1 = self.box_1
							self.box_1 = filtered_boxes[i]
							self.prev_first_hand_shape = self.first_hand_shape
							self.first_hand_shape = filtered_classes[i];
							self.gestures_queue_first.queue.clear()
							self.gestures_queue_second.queue.clear()

							for j in range(3):
								self.gestures_queue_first.put(-1)
								self.gestures_queue_second.put(-1)

						if not list(self.gestures_queue_first.queue)[2] == detector_utils.is_hand_opened(filtered_classes[i]):
							self.gestures_queue_first.get()
							self.gestures_queue_first.put(detector_utils.is_hand_opened(filtered_classes[i]));

							# print list(self.gestures_queue_first.queue)

						# print '#boxes: ',len(filtered_boxes) 
						if len(filtered_boxes)==1 and detector_utils.check_pattern(self.gestures_queue_first.queue,self.connect_pattern,self.connect_pattern) and not self.is_connected:
							print 'Connect'
							self.is_connected = True;

						cv2.rectangle(image_np, p1, p2, (255, 0, 0), 1,)
						cv2.putText(image_np,str(filtered_classes[i]),(int(left)-5, int(top)-5),cv2.FONT_HERSHEY_SIMPLEX,1,255)

					if accepted_hands_count == 2:
						self.prev_second_hand_shape = self.second_hand_shape
						self.second_hand_shape = filtered_classes[i];

						self.prev_box_2 = self.box_2;
						self.box_2 = filtered_boxes[i]

						self.second_sample_points_xy = [(int(left+width/4),int(top+height/4)),
												(int(right-width/4),int(top+height/4)),
												(int(left+width/4),int(bottom-height/4)),
												(int(right-width/4),int(bottom-height/4)),
												(int(right-width/2),int(bottom-height/2))]

						if self.first_hand_shape ==6.0 and self.second_hand_shape == 6.0:
							if self.first_sample_points_xy[0][0]>self.second_sample_points_xy[0][0]:
								image_np = detector_utils.draw_steering_wheel(image_np,self.first_sample_points_xy[0][1]-self.second_sample_points_xy[0][1])
							else:
								image_np = detector_utils.draw_steering_wheel(image_np,self.second_sample_points_xy[0][1]-self.first_sample_points_xy[0][1])
						# else:
						# 	print self.first_hand_shape,self.second_hand_shape

						for k in range(5):
							cv2.circle(image_np,self.second_sample_points_xy[k], 2, (0,0,255), -1)
							cv2.line(image_np,self.prev_second_sample_points_xy[k],self.second_sample_points_xy[k],(255,0,0),1)
						self.prev_second_sample_points_xy = self.second_sample_points_xy
						cv2.rectangle(image_np, p1, p2, (0, 0, 255), 1)
						cv2.putText(image_np,str(filtered_classes[i]),(int(left)-5, int(top)-5),cv2.FONT_HERSHEY_SIMPLEX,1,255)

						'''
				# image_np = detector_utils.draw_steering_wheel(image_np,50)
				image_np = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR);
				self.output_img=image_np#[0:image_np.shape[0],0:image_np.shape[1],:]=image_np;

		except RuntimeError, e:
			print("[INFO] caught a RuntimeError")


if __name__ == '__main__':
	video_stream = cv2.VideoCapture(0)
	video_stream.set(cv2.CAP_PROP_FRAME_WIDTH, 600)
	video_stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)
	 
	start_time = datetime.datetime.now()
	num_frames = 0


	# start the app
	hgd = hand_gesture_detector(video_stream)
	hgd.root.mainloop()




