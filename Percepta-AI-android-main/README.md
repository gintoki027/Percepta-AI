# YOLOv8 Object Detection with Distance Estimation & TTS

An Android application that performs real-time object detection using YOLOv8 (TFLite), estimates the distance of objects, and provides accessibility features through Text-to-Speech (TTS) and Voice Search.

## 🚀 Features

*   **Real-time Object Detection:** Powered by YOLOv8 and TensorFlow Lite.
*   **Distance Estimation:** Heuristic-based calculation to estimate how far objects are from the camera.
*   **Smart Text-to-Speech (TTS):**
    *   Automatically alerts the user when an object is "very close" (less than 1 meter).
    *   Intelligent filtering: Only announces new objects entering the proximity zone to avoid repetitive spam.
*   **Voice Search:** Users can ask the app to find specific objects (e.g., "Find chair") via voice commands.
*   **CameraX Integration:** High-performance camera preview and image analysis.

## 🛠️ Tech Stack

*   **Language:** Kotlin
*   **Machine Learning:** TensorFlow Lite
*   **Camera API:** Jetpack CameraX
*   **Speech Services:** Android TTS and Speech Recognizer
*   **UI:** View Binding, AppCompat, Material Design

## 📋 Prerequisites

*   Android Studio Hedgehog or newer.
*   Android device running API 21 (Lollipop) or higher.
*   Camera and Microphone permissions for core functionality.

## 📦 Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/Object-Detection-Android-App.git
    ```
2.  **Open in Android Studio:**
    Import the project located in `android_app/android_app`.
3.  **Model Assets:**
    Ensure `model.tflite` and `labels.txt` are present in the `app/src/main/assets` directory.
4.  **Build and Run:**
    Connect your device and click the "Run" button in Android Studio.

## ⚙️ How it Works

### Distance Estimation
The app uses a heuristic based on the known real-world height of common objects and their apparent height in the camera frame to estimate distance.

### Smart Alerts
In `MainActivity.kt`, the app tracks objects detected within 1 meter. It maintains a state of "spoken" objects to ensure that if a person stands in front of the camera, the app doesn't repeatedly say "Person is very close" every second, but rather alerts the user once when the person first appears.

### Voice Interaction
By clicking the search button, users can use natural language to query the scene. The app matches the spoken word against current detections and provides audio feedback on the object's presence and distance.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
