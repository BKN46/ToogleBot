import base64

def read_base64_pic(jpeg_b64_str: str) -> bytes:
    content = base64.b64decode(jpeg_b64_str)
    return content


def get_base64_encode(jpeg_btye: bytes) -> str:
    return base64.b64encode(jpeg_btye).decode("utf-8")
