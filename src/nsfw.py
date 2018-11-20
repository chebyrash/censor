from io import BytesIO

import caffe
import numpy as np
from PIL import Image


def resize_image(img_data, size=(256, 256)):
    im = Image.open(BytesIO(img_data))
    if im.mode != "RGB":
        im = im.convert("RGB")
    imr = im.resize(size, resample=Image.BILINEAR)
    fh_im = BytesIO()
    imr.save(fh_im, format="JPEG")
    fh_im.seek(0)
    return bytearray(fh_im.read())


def caffe_preprocess_and_compute(pimg, caffe_transformer=None, caffe_net=None, output_layers=None):
    if caffe_net is not None:
        if output_layers is None:
            output_layers = caffe_net.outputs

        img_data_rs = resize_image(pimg, size=(256, 256))
        image = caffe.io.load_image(BytesIO(img_data_rs))

        H, W, _ = image.shape
        _, _, h, w = caffe_net.blobs["data"].data.shape
        h_off = max((H - h) // 2, 0)
        w_off = max((W - w) // 2, 0)
        crop = image[h_off:h_off + h, w_off:w_off + w, :]
        transformed_image = caffe_transformer.preprocess("data", crop)
        transformed_image.shape = (1,) + transformed_image.shape

        input_name = caffe_net.inputs[0]
        all_outputs = caffe_net.forward_all(blobs=output_layers,
                                            **{input_name: transformed_image})

        outputs = all_outputs[output_layers[0]][0].astype(float)
        return outputs
    else:
        return []


def load_model(model_def=None, pretrained_model=None):
    if model_def is None:
        model_def = "deploy.prototxt"
    if pretrained_model is None:
        pretrained_model = "resnet_50_1by2_nsfw.caffemodel"
    nsfw_net = caffe.Net(model_def, pretrained_model, caffe.TEST)
    caffe_transformer = caffe.io.Transformer({"data": nsfw_net.blobs["data"].data.shape})
    caffe_transformer.set_transpose("data", (2, 0, 1))
    caffe_transformer.set_mean("data", np.array([104, 117, 123]))
    caffe_transformer.set_raw_scale("data", 255)
    caffe_transformer.set_channel_swap("data", (2, 1, 0))
    return nsfw_net, caffe_transformer
