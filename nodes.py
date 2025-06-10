import os
import json
import piexif
from datetime import datetime
import torch
import numpy as np
from pathlib import Path
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS, IFD
from PIL.PngImagePlugin import PngImageFile
from PIL.JpegImagePlugin import JpegImageFile


## copy from https://github.com/crystian/ComfyUI-Crystools/blob/main/nodes/image.py
## change the input type and output
## ========== main ==========##
class ZLoadImageWithMetaData:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "filepath": ("STRING", {"lazy": True, "default": "input/example.png"}),
            },
        }

    CATEGORY = "LoadImageWithMetadataEx"
    RETURN_TYPES = ("IMAGE", "METADATA_RAW")
    RETURN_NAMES = ("image", "Metadata RAW")
    OUTPUT_NODE = True

    FUNCTION = "execute"

    def execute(self, filepath):
        image_path = filepath  # use the string as image_path

        imgF = Image.open(image_path)
        img, prompt, metadata = buildMetadata(image_path)
        

        if imgF.format == 'WEBP':
            try:
                exif_data = piexif.load(image_path)
                prompt, metadata = self.process_exif_data(exif_data)
            except ValueError:
                pass

        img = ImageOps.exif_transpose(img)
        image = img.convert("RGB")
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]

        return image, metadata

    def process_exif_data(self, exif_data):
        metadata = {}
        if '0th' in exif_data and 271 in exif_data['0th']:
            prompt_data = exif_data['0th'][271].decode('utf-8')
            prompt_data = prompt_data.replace('Prompt:', '', 1)
            try:
                metadata['prompt'] = json.loads(prompt_data)
            except json.JSONDecodeError:
                metadata['prompt'] = prompt_data

        if '0th' in exif_data and 270 in exif_data['0th']:
            workflow_data = exif_data['0th'][270].decode('utf-8')
            workflow_data = workflow_data.replace('Workflow:', '', 1)
            try:
                metadata['workflow'] = json.loads(workflow_data)
            except json.JSONDecodeError:
                metadata['workflow'] = workflow_data

        metadata.update(exif_data)
        return metadata
    
    def check_lazy_status(self, filepath):
        return ["filepath"]


def buildMetadata(image_path):
    if Path(image_path).is_file() is False:
        raise Exception("TEXTS.FILE_NOT_FOUND.value")

    img = Image.open(image_path)

    metadata = {}
    prompt = {}

    metadata["fileinfo"] = {
        "filename": Path(image_path).as_posix(),
        "resolution": f"{img.width}x{img.height}",
        "date": str(datetime.fromtimestamp(os.path.getmtime(image_path))),
        "size": str(get_size(image_path)),
    }

    # only for png files
    if isinstance(img, PngImageFile):
        metadataFromImg = img.info

        # for all metadataFromImg convert to string (but not for workflow and prompt!)
        for k, v in metadataFromImg.items():
            # from ComfyUI
            if k == "workflow":
                try:
                    metadata["workflow"] = json.loads(metadataFromImg["workflow"])
                except Exception as e:
                    pass

            # from ComfyUI
            elif k == "prompt":
                try:
                    metadata["prompt"] = json.loads(metadataFromImg["prompt"])

                    # extract prompt to use on metadataFromImg
                    prompt = metadata["prompt"]
                except Exception as e:
                    pass

            else:
                try:
                    # for all possible metadataFromImg by user
                    metadata[str(k)] = json.loads(v)
                except Exception as e:
                    try:
                        metadata[str(k)] = str(v)
                    except Exception as e:
                        pass

    if isinstance(img, JpegImageFile):
        exif = img.getexif()

        for k, v in exif.items():
            tag = TAGS.get(k, k)
            if v is not None:
                metadata[str(tag)] = str(v)

        for ifd_id in IFD:
            try:
                if ifd_id == IFD.GPSInfo:
                    resolve = GPSTAGS
                else:
                    resolve = TAGS

                ifd = exif.get_ifd(ifd_id)
                ifd_name = str(ifd_id.name)
                metadata[ifd_name] = {}

                for k, v in ifd.items():
                    tag = resolve.get(k, k)
                    metadata[ifd_name][str(tag)] = str(v)

            except KeyError:
                pass

    return img, prompt, metadata

def get_size(path):
    size = os.path.getsize(path)
    if size < 1024:
        return f"{size} bytes"
    elif size < pow(1024, 2):
        return f"{round(size / 1024, 2)} KB"
    elif size < pow(1024, 3):
        return f"{round(size / (pow(1024, 2)), 2)} MB"
    elif size < pow(1024, 4):
        return f"{round(size / (pow(1024, 3)), 2)} GB"