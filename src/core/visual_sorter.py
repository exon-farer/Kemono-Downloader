import os
import csv
import threading
import numpy as np
from PIL import Image
from PyQt5.QtCore import QSettings # Added to read the saved threshold

class VisualSorter:
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, model_path, csv_path):
        if cls._instance is None:
            with cls._lock: 
                if cls._instance is None:
                    cls._instance = cls(model_path, csv_path)
        return cls._instance

    def __init__(self, model_path, csv_path):
        import onnxruntime as ort 
        providers = ["CPUExecutionProvider"]
        self.model = ort.InferenceSession(model_path, providers=providers)
        
        self.tags = []
        self.character_start_idx = None
        self.character_end_idx = None
        
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                tag_name = row[1].replace("_", " ").lower()
                category = row[2]
                if category == "4" and self.character_start_idx is None:
                    self.character_start_idx = reader.line_num - 2
                elif category != "4" and self.character_start_idx is not None and self.character_end_idx is None:
                    self.character_end_idx = reader.line_num - 2
                self.tags.append(tag_name)
                
        if self.character_end_idx is None:
            self.character_end_idx = len(self.tags)

    def get_current_threshold(self):
        """Fetches the latest threshold setting and converts it to a float."""
        settings = QSettings("MediaDownloader", "VisualSort")
        # Read the integer percentage, default to 50 if it doesn't exist yet
        threshold_pct = settings.value("char_threshold", 50, type=int)
        # Convert 50% into the 0.50 float required by the ONNX model
        return threshold_pct / 100.0

    def process_image(self, image_path):
        with self._lock: 
            try:
                with Image.open(image_path) as image:
                    if getattr(image, "is_animated", False):
                        image.seek(0)
                    image = image.convert('RGB')
                    
                    input_layer = self.model.get_inputs()[0]
                    target_size = input_layer.shape[1]
                    ratio = float(target_size) / max(image.size)
                    new_size = tuple([int(x * ratio) for x in image.size])
                    image_resized = image.resize(new_size, Image.LANCZOS)
                    square = Image.new("RGB", (target_size, target_size), (255, 255, 255))
                    square.paste(image_resized, ((target_size - new_size[0]) // 2, (target_size - new_size[1]) // 2))
                    
                    image_array = np.array(square).astype(np.float32)
                    image_array = image_array[:, :, ::-1]
                    image_array = np.expand_dims(image_array, axis=0)
                    
                    input_name = input_layer.name
                    preds = self.model.run(None, {input_name: image_array})[0][0]
                    
                    char_preds = preds[self.character_start_idx:self.character_end_idx]
                    char_tags = self.tags[self.character_start_idx:self.character_end_idx]
                    
                    # Get the dynamic threshold for this specific evaluation
                    current_threshold = self.get_current_threshold()
                    
                    if len(char_tags) == 0:
                        return {"best_char": None, "reason": "predicted character not present in tag database", "threshold": current_threshold}

                    # Get top 3 characters using numpy
                    top_char_indices = np.argsort(char_preds)[::-1][:3]
                    top_3_chars = [(char_tags[i].title(), float(char_preds[i])) for i in top_char_indices]
                    
                    max_char_score = top_3_chars[0][1] if top_3_chars else 0
                    
                    result = {
                        "best_char": None,
                        "top_3_chars": top_3_chars,
                        "threshold": current_threshold,
                        "reason": "",
                        "top_tags": []
                    }
                    
                    # Heuristics to determine the reason
                    if max_char_score < 0.15: # Very low confidence overall indicates no character
                        # Get general tags for the log (excluding characters)
                        general_preds = preds[:self.character_start_idx]
                        general_tags = self.tags[:self.character_start_idx]
                        top_general_indices = np.argsort(general_preds)[::-1][:3]
                        result["top_tags"] = [(general_tags[i], float(general_preds[i])) for i in top_general_indices]
                        result["reason"] = "no character detected"
                    elif max_char_score > current_threshold:
                        result["best_char"] = top_3_chars[0][0]
                        result["reason"] = "success"
                    else:
                        # Max score is between 0.15 and current_threshold
                        if len(top_3_chars) > 1 and top_3_chars[1][1] > (max_char_score * 0.7):
                            result["reason"] = "multiple characters but none above threshold"
                        else:
                            result["reason"] = "confidence below threshold"
                            
                    return result
         
            except Exception as e:
                print(f"ONNX Evaluation Error: {e}")
                return None