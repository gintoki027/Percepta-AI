package com.percepta.yolov8tflite

import android.content.Context
import android.graphics.Bitmap
import android.os.SystemClock
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.support.common.FileUtil
import org.tensorflow.lite.support.common.ops.CastOp
import org.tensorflow.lite.support.common.ops.NormalizeOp
import org.tensorflow.lite.support.image.ImageProcessor
import org.tensorflow.lite.support.image.TensorImage
import org.tensorflow.lite.support.tensorbuffer.TensorBuffer
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStream
import java.io.InputStreamReader

class Detector(
    private val context: Context,
    private val modelPath: String,
    private val labelPath: String,
    private val detectorListener: DetectorListener
) {

    private var interpreter: Interpreter? = null
    private var labels = mutableListOf<String>()

    private var tensorWidth = 0
    private var tensorHeight = 0
    private var numChannel = 0
    private var numElements = 0

    private val imageProcessor = ImageProcessor.Builder()
        .add(NormalizeOp(INPUT_MEAN, INPUT_STANDARD_DEVIATION))
        .add(CastOp(INPUT_IMAGE_TYPE))
        .build()

    fun setup() {
        val model = FileUtil.loadMappedFile(context, modelPath)
        val options = Interpreter.Options()
        options.numThreads = 4
        interpreter = Interpreter(model, options)

        val inputShape = interpreter?.getInputTensor(0)?.shape() ?: return
        val outputShape = interpreter?.getOutputTensor(0)?.shape() ?: return

        tensorWidth = inputShape[1]
        tensorHeight = inputShape[2]
        numChannel = outputShape[1]
        numElements = outputShape[2]

        try {
            val inputStream: InputStream = context.assets.open(labelPath)
            val reader = BufferedReader(InputStreamReader(inputStream))

            var line: String? = reader.readLine()
            while (line != null && line != "") {
                labels.add(line)
                line = reader.readLine()
            }

            reader.close()
            inputStream.close()
        } catch (e: IOException) {
            e.printStackTrace()
        }
    }

    fun clear() {
        interpreter?.close()
        interpreter = null
    }

    fun detect(frame: Bitmap) {
        interpreter ?: return
        if (tensorWidth == 0) return
        if (tensorHeight == 0) return
        if (numChannel == 0) return
        if (numElements == 0) return

        var inferenceTime = SystemClock.uptimeMillis()

        val resizedBitmap = Bitmap.createScaledBitmap(frame, tensorWidth, tensorHeight, false)

        val tensorImage = TensorImage(DataType.FLOAT32)
        tensorImage.load(resizedBitmap)
        val processedImage = imageProcessor.process(tensorImage)
        val imageBuffer = processedImage.buffer

        val output = TensorBuffer.createFixedSize(intArrayOf(1 , numChannel, numElements), OUTPUT_IMAGE_TYPE)
        interpreter?.run(imageBuffer, output.buffer)


        val bestBoxes = bestBox(output.floatArray)
        inferenceTime = SystemClock.uptimeMillis() - inferenceTime


        if (bestBoxes == null) {
            detectorListener.onEmptyDetect()
            return
        }

        detectorListener.onDetect(bestBoxes, inferenceTime)
    }

    private fun bestBox(array: FloatArray) : List<BoundingBox>? {

        val boundingBoxes = mutableListOf<BoundingBox>()

        for (c in 0 until numElements) {
            var maxConf = -1.0f
            var maxIdx = -1
            var j = 4
            var arrayIdx = c + numElements * j
            while (j < numChannel){
                if (array[arrayIdx] > maxConf) {
                    maxConf = array[arrayIdx]
                    maxIdx = j - 4
                }
                j++
                arrayIdx += numElements
            }

            if (maxConf > CONFIDENCE_THRESHOLD) {
                val clsName = if (maxIdx < labels.size) labels[maxIdx] else "Unknown"
                val cx = array[c]
                val cy = array[c + numElements]
                val w = array[c + numElements * 2]
                val h = array[c + numElements * 3]
                
                val x1 = cx - (w/2F)
                val y1 = cy - (h/2F)
                val x2 = cx + (w/2F)
                val y2 = cy + (h/2F)
                
                // Only skip if the box is completely out of view or degenerate
                if (x1 > 1f || x2 < 0f || y1 > 1f || y2 < 0f) continue

                // Heuristic for distance: Distance = (Real Object Height * k) / Apparent Object Height
                val realHeight = getRealHeight(clsName)
                
                // k is a constant related to the camera's focal length and vertical field of view.
                // Adjusted to 0.5f for better accuracy at close range.
                val k = 0.5f
                val estimatedDistance = (realHeight * k) / (h + 0.0001f)

                boundingBoxes.add(
                    BoundingBox(
                        x1 = x1.coerceIn(0f, 1f), 
                        y1 = y1.coerceIn(0f, 1f), 
                        x2 = x2.coerceIn(0f, 1f), 
                        y2 = y2.coerceIn(0f, 1f),
                        cx = cx, cy = cy, w = w, h = h,
                        cnf = maxConf, cls = maxIdx, clsName = clsName,
                        distance = estimatedDistance
                    )
                )
            }
        }

        if (boundingBoxes.isEmpty()) return null

        return applyNMS(boundingBoxes)
    }

    private fun getRealHeight(clsName: String): Float {
        return when (clsName) {
            "person" -> 1.7f
            "bicycle" -> 1.0f
            "car" -> 1.5f
            "motorcycle" -> 1.0f
            "airplane" -> 4.0f
            "bus" -> 3.0f
            "train" -> 3.5f
            "truck" -> 2.5f
            "boat" -> 2.0f
            "traffic light" -> 0.8f
            "fire hydrant" -> 0.6f
            "stop sign" -> 0.75f
            "parking meter" -> 1.2f
            "bench" -> 0.5f
            "bird" -> 0.15f
            "cat" -> 0.25f
            "dog" -> 0.5f
            "horse" -> 1.6f
            "sheep" -> 0.8f
            "cow" -> 1.5f
            "elephant" -> 3.0f
            "bear" -> 1.5f
            "zebra" -> 1.3f
            "giraffe" -> 5.0f
            "backpack" -> 0.45f
            "umbrella" -> 0.6f
            "handbag" -> 0.3f
            "tie" -> 0.4f
            "suitcase" -> 0.6f
            "frisbee" -> 0.03f
            "skis" -> 0.05f
            "snowboard" -> 0.05f
            "sports ball" -> 0.2f
            "kite" -> 0.5f
            "baseball bat" -> 0.8f
            "baseball glove" -> 0.2f
            "skateboard" -> 0.1f
            "surfboard" -> 0.05f
            "tennis racket" -> 0.6f
            "bottle" -> 0.25f
            "wine glass" -> 0.2f
            "cup" -> 0.12f
            "fork", "knife", "spoon" -> 0.2f
            "bowl" -> 0.1f
            "banana", "apple", "sandwich", "orange", "broccoli", "carrot" -> 0.1f
            "hot dog", "pizza", "donut", "cake" -> 0.05f
            "chair" -> 0.9f
            "couch" -> 0.8f
            "potted plant" -> 0.4f
            "bed" -> 0.6f
            "dining table" -> 0.75f
            "toilet" -> 0.4f
            "tv" -> 0.5f
            "laptop" -> 0.25f
            "mouse" -> 0.05f
            "remote" -> 0.15f
            "keyboard" -> 0.05f
            "cell phone" -> 0.15f
            "microwave", "oven" -> 0.4f
            "toaster" -> 0.2f
            "sink" -> 0.2f
            "refrigerator" -> 1.7f
            "book" -> 0.25f
            "clock" -> 0.3f
            "vase" -> 0.3f
            "scissors" -> 0.2f
            "teddy bear" -> 0.3f
            "hair drier" -> 0.2f
            "toothbrush" -> 0.18f
            else -> 0.5f
        }
    }

    private fun applyNMS(boxes: List<BoundingBox>) : MutableList<BoundingBox> {
        val sortedBoxes = boxes.sortedByDescending { it.cnf }.toMutableList()
        val selectedBoxes = mutableListOf<BoundingBox>()

        while(sortedBoxes.isNotEmpty()) {
            val first = sortedBoxes.first()
            selectedBoxes.add(first)
            sortedBoxes.remove(first)

            val iterator = sortedBoxes.iterator()
            while (iterator.hasNext()) {
                val nextBox = iterator.next()
                val iou = calculateIoU(first, nextBox)
                if (iou >= IOU_THRESHOLD) {
                    iterator.remove()
                }
            }
        }

        return selectedBoxes
    }

    private fun calculateIoU(box1: BoundingBox, box2: BoundingBox): Float {
        val x1 = maxOf(box1.x1, box2.x1)
        val y1 = maxOf(box1.y1, box2.y1)
        val x2 = minOf(box1.x2, box2.x2)
        val y2 = minOf(box1.y2, box2.y2)
        val intersectionArea = maxOf(0F, x2 - x1) * maxOf(0F, y2 - y1)
        val box1Area = box1.w * box1.h
        val box2Area = box2.w * box2.h
        return intersectionArea / (box1Area + box2Area - intersectionArea)
    }

    interface DetectorListener {
        fun onEmptyDetect()
        fun onDetect(boundingBoxes: List<BoundingBox>, inferenceTime: Long)
    }

    companion object {
        private const val INPUT_MEAN = 0f
        private const val INPUT_STANDARD_DEVIATION = 255f
        private val INPUT_IMAGE_TYPE = DataType.FLOAT32
        private val OUTPUT_IMAGE_TYPE = DataType.FLOAT32
        private const val CONFIDENCE_THRESHOLD = 0.3F
        private const val IOU_THRESHOLD = 0.5F
    }
}
