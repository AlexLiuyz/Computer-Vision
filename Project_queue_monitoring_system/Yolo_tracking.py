# -*- coding: utf-8 -*-
"""main.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/11Ek1QqWwqsUtlDkSe10uuxBVUPdadqvD
"""

from google.colab import drive
drive.mount('/content/drive')

# !pip install -r requirements.txt
# !pip install tqdm gradio
!pip install ultralytics
import os
os.chdir('/content/drive/MyDrive/Colab Notebooks/Project/yolov8-deepsort-tracking-main')
import tempfile
from pathlib import Path
import numpy as np
import cv2 # opencv-python
from ultralytics import YOLO

import deep_sort.deep_sort.deep_sort as ds

# Commented out IPython magic to ensure Python compatibility.
# !pip install nbimporter
import os
import importlib
# Import code from other_notebook.ipynb
os.chdir('/content/drive/MyDrive/Colab Notebooks/Project/')
# %run VGG_net.ipynb
# from Classifier import VGGFeature

from sklearn import svm
import joblib
# Load the pretrained model state dictionary
# pretrained_model_path = "/content/drive/MyDrive/Colab Notebooks/Project/output_model/vgg_extractor.pt"
pretrained_model_path = "/content/drive/MyDrive/Colab Notebooks/Project/output_model/3_class_vgg_extractor.pt"
vgg_model = torch.load(pretrained_model_path)
pretrained_model_path = "/content/drive/MyDrive/Colab Notebooks/Project/output_model/3_class_SVM_model.pkl"
svm_model = joblib.load(pretrained_model_path)



import os
import cv2
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
import torchvision.transforms as transforms

norm_mean = [0.485, 0.456, 0.406]
norm_std = [0.229, 0.224, 0.225]

inference_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.ToTensor(),
    transforms.Normalize(norm_mean, norm_std),
])

def img_transform(img_rgb, transform=None):
    """
    transform images
    :param img_rgb: PIL Image
    :param transform: torchvision.transform
    :return: tensor
    """

    if transform is None:
        raise ValueError("there is no transform")

    img_t = transform(Image.fromarray(img_rgb))
    return img_t
labels={0:'not_queue',1:'queuing',2:'serving'}
cat={'not_queue':0, 'queuing':1, 'serving':2}

import torch
def putTextWithBackground(img, text, origin, font=cv2.FONT_HERSHEY_SIMPLEX, font_scale=1, text_color=(255, 255, 255), bg_color=(0, 0, 0), thickness=1):
    """绘制带有背景的文本。

    :param img: 输入图像。
    :param text: 要绘制的文本。
    :param origin: 文本的左上角坐标。
    :param font: 字体类型。
    :param font_scale: 字体大小。
    :param text_color: 文本的颜色。
    :param bg_color: 背景的颜色。
    :param thickness: 文本的线条厚度。
    """
    # 计算文本的尺寸
    (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, thickness)

    # 绘制背景矩形
    bottom_left = origin
    top_right = (origin[0] + text_width, origin[1] - text_height - 5)  # 减去5以留出一些边距
    cv2.rectangle(img, bottom_left, top_right, bg_color, -1)

    # 在矩形上绘制文本
    text_origin = (origin[0], origin[1] - 5)  # 从左上角的位置减去5来留出一些边距
    cv2.putText(img, text, text_origin, font, font_scale, text_color, thickness, lineType=cv2.LINE_AA)

def extract_detections(results, detect_class):
    """
    从模型结果中提取和处理检测信息。
    - results: YoloV8模型预测结果，包含检测到的物体的位置、类别和置信度等信息。
    - detect_class: 需要提取的目标类别的索引。
    参考: https://docs.ultralytics.com/modes/predict/#working-with-results
    """

    # 初始化一个空的二维numpy数组，用于存放检测到的目标的位置信息
    # 如果视频中没有需要提取的目标类别，如果不初始化，会导致tracker报错
    detections = np.empty((0, 4))

    confarray = [] # 初始化一个空列表，用于存放检测到的目标的置信度。

    # 遍历检测结果
    # 参考：https://docs.ultralytics.com/modes/predict/#working-with-results
    for r in results:
        for box in r.boxes:
            # 如果检测到的目标类别与指定的目标类别相匹配，提取目标的位置信息和置信度
            if box.cls[0].int() == detect_class:
                x1, y1, x2, y2 = box.xywh[0].int().tolist() # 提取目标的位置信息，并从tensor转换为整数列表。
                conf = round(box.conf[0].item(), 2) # 提取目标的置信度，从tensor中取出浮点数结果，并四舍五入到小数点后两位。
                detections = np.vstack((detections, np.array([x1, y1, x2, y2]))) # 将目标的位置信息添加到detections数组中。
                confarray.append(conf) # 将目标的置信度添加到confarray列表中。
    return detections, confarray # 返回提取出的位置信息和置信度。

# 视频处理
def detect_and_track(input_path: str, output_path: str, detect_class: int, model, tracker) -> Path:
    cap = cv2.VideoCapture(input_path)  # 使用OpenCV打开视频文件。
    if not cap.isOpened():  # 检查视频文件是否成功打开。
        print(f"Error opening video file {input_path}")
        return None
    orange=(245, 147, 66)
    fps = cap.get(cv2.CAP_PROP_FPS)  # 获取视频的帧率
    size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))) # 获取视频的分辨率（宽度和高度）。
    output_video_path =output_path+ "output.mp4" # 设置输出视频的保存路径。

    # 设置视频编码格式为XVID格式的avi文件
    # 如果需要使用h264编码或者需要保存为其他格式，可能需要下载openh264-1.8.0
    # 下载地址：https://github.com/cisco/openh264/releases/tag/v1.8.0
    # 下载完成后将dll文件放在当前文件夹内
    fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
    # cv2.VideoWriter('/content/drive/MyDrive/Colab Notebooks/Project/output.mp4', fourcc, fps, size)
    output_video = cv2.VideoWriter(output_video_path, fourcc, fps, size, isColor=True) # 创建一个VideoWriter对象用于写视频。
    i=0
    # 对每一帧图片进行读取和处理
    while True:
        success, frame = cap.read() # 逐帧读取视频。

        # 如果读取失败（或者视频已处理完毕），则跳出循环。
        if not (success):
            break
        # if(i>20):
        #   break
        # 使用YoloV8模型对当前帧进行目标检测。
        results = model(frame, stream=True)
        i+=1
        # 从预测结果中提取检测信息。
        detections, confarray = extract_detections(results, detect_class)

        # 使用deepsort模型对检测到的目标进行跟踪。
        resultsTracker = tracker.update(detections, confarray, frame)
        num_ones=0
        num_twos=0
        colors=((255, 0, 0),(0, 255, 0),(0, 0, 255),(255, 0, 255))
        for x1, y1, x2, y2, Id in resultsTracker:
            x1, y1, x2, y2 = map(int, [x1, y1, x2, y2]) # 将位置信息转换为整数。
            cropped_frame = frame[y1:y2, x1:x2]
            # samples.append(Sample(img=img_transform(cv2.resize(cropped_img,(200,300)), inference_transform)))
            train_feat=img_transform(cv2.resize(cropped_frame,(200,300)), inference_transform)
            train_feat = torch.tensor(train_feat).to(torch.float32)
            train_x = torch.reshape(train_feat,[1,3,384,256])
            result,conv=vgg_model(train_x.cuda().requires_grad_(False))
            torch.cuda.empty_cache()
            prediction = svm_model.predict(conv.detach().cpu().requires_grad_(False))
            # 绘制bounding box和文本
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 3)
            text=str(int(Id))+": "+labels[prediction[0]]
            if(prediction[0]==1):
              num_ones+=1
            if(prediction[0]==2):
              num_twos+=1
            putTextWithBackground(frame, text, (max(-10, x1), max(40, y1)), font_scale=1, text_color=(255, 255, 255), bg_color=colors[prediction[0]])
        if(num_twos==0):
          opt_time=num_ones*5
        else:
          opt_time=num_ones*5//num_twos
        cv2.putText(frame, f"queuing People: {num_ones}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.75, orange, 2)
        cv2.putText(frame, f"WaitingTime: {num_ones*5}s", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.75, orange, 2)
        cv2.putText(frame, f"Num_server: {num_twos}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.75, orange, 2)
        cv2.putText(frame, f"Optimal WaitingTime: {opt_time}s", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.75, orange, 2)
        output_video.write(frame)  # 将处理后的帧写入到输出视频文件中。

    output_video.release()  # 释放VideoWriter对象。
    cap.release()  # 释放视频文件。

    # print(f'output dir is: {output_video_path}')
    return output_video_path

if __name__ == "__main__":
    # 指定输入视频的路径。
    ######
    input_path = "video.mp4"
    ######

    # 输出文件夹，默认为系统的临时文件夹路径
    output_path = "/content/drive/MyDrive/Colab Notebooks/Project/yolov8-deepsort-tracking-main/"  # 创建一个临时目录用于存放输出视频。

    # 加载yoloV8模型权重
    model = YOLO("yolov8n.pt")

    # 设置需要检测和跟踪的目标类别
    # yoloV8官方模型的第一个类别为'person'
    detect_class = 0
    # print(f"detecting {model.names[detect_class]}") # model.names返回模型所支持的所有物体类别

    # 加载DeepSort模型
    tracker = ds.DeepSort("/content/drive/MyDrive/Colab Notebooks/Project/yolov8-deepsort-tracking-main/deep_sort/deep_sort/deep/checkpoint/ckpt.t7")

    detect_and_track(input_path, output_path, detect_class, model, tracker)