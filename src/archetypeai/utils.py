import base64


def base64_encode(filename: str) -> str:
    with open(filename, "rb") as img_handle:
        encoded_img = base64.b64encode(img_handle.read()).decode("utf-8")
    return encoded_img