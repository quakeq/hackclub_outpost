# Stickify
Our project captures the position of a person's head, arm, hands, legs, and foot through OpenCV. 
The detected position is sent to the 16*16 LED matrix to display as a stick figure. 
This project originally was intended to work in tandem with a 3D volumetric display, but due to time constraints, it is currently implemented on a 2D LED Matrix. 
## Capturing
We host a local network with a laptop's hotspot, and data is sent to, processed by, and sent out by the host laptop. We created an android app that sends live video data to the host laptop. In the laptop, the data is then processed using OpenCV to track the position of each limb of a person. The system includes wireless access from multiple devices. This is to support future expansion into capturing and displaying 3D data captured across devices. 
## Display
The display is a 16x16 LED matrix that is a linkage of 4 8x8 LED Matricies. The power is daisy chained, but each LED panel has a dedicated GPIO output from the ESP32 S3. 
## Volumetric Display
is it gon work???
## BOM
|material|qty|
|8x8 P10 LED Matrix|4x|
|NEMA 17 Stepper Motor|1x|
|ESP 32 S3|1x|
|Raspberry Pi Pico|1x|
|A4988|1x|

