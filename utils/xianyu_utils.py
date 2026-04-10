import json
import time
import hashlib
import base64
import struct
from typing import Any, Dict, List


def trans_cookies(cookies_str: str) -> Dict[str, str]:
    """解析cookie字符串为字典"""
    cookies = {}
    for cookie in cookies_str.split("; "):
        try:
            if not cookie:  # 跳过空字符串
                continue
            parts = cookie.split('=', 1)
            if len(parts) == 2 and parts[0]:  # 确保key不为空
                cookies[parts[0]] = parts[1]
        except:
            continue
    return cookies


def generate_mid() -> str:
    """生成mid"""
    import random
    random_part = int(1000 * random.random())
    timestamp = int(time.time() * 1000)
    return f"{random_part}{timestamp} 0"


def generate_uuid() -> str:
    """生成uuid"""
    timestamp = int(time.time() * 1000)
    return f"-{timestamp}1"


def generate_device_id(user_id: str) -> str:
    """生成设备ID"""
    import random
    
    # 字符集
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    result = []
    
    for i in range(36):
        if i in [8, 13, 18, 23]:
            result.append("-")
        elif i == 14:
            result.append("4")
        else:
            if i == 19:
                # 对于位置19，需要特殊处理
                rand_val = int(16 * random.random())
                result.append(chars[(rand_val & 0x3) | 0x8])
            else:
                rand_val = int(16 * random.random())
                result.append(chars[rand_val])
    
    return ''.join(result) + "-" + user_id


def generate_sign(t: str, token: str, data: str) -> str:
    """生成签名"""
    app_key = "34839810"
    msg = f"{token}&{t}&{app_key}&{data}"
    
    # 使用MD5生成签名
    md5_hash = hashlib.md5()
    md5_hash.update(msg.encode('utf-8'))
    return md5_hash.hexdigest()


class MessagePackDecoder:
    """MessagePack解码器的纯Python实现"""
    
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.length = len(data)
    
    def read_byte(self) -> int:
        if self.pos >= self.length:
            raise ValueError("Unexpected end of data")
        byte = self.data[self.pos]
        self.pos += 1
        return byte
    
    def read_bytes(self, count: int) -> bytes:
        if self.pos + count > self.length:
            raise ValueError("Unexpected end of data")
        result = self.data[self.pos:self.pos + count]
        self.pos += count
        return result
    
    def read_uint8(self) -> int:
        return self.read_byte()
    
    def read_uint16(self) -> int:
        return struct.unpack('>H', self.read_bytes(2))[0]
    
    def read_uint32(self) -> int:
        return struct.unpack('>I', self.read_bytes(4))[0]
    
    def read_uint64(self) -> int:
        return struct.unpack('>Q', self.read_bytes(8))[0]
    
    def read_int8(self) -> int:
        return struct.unpack('>b', self.read_bytes(1))[0]
    
    def read_int16(self) -> int:
        return struct.unpack('>h', self.read_bytes(2))[0]
    
    def read_int32(self) -> int:
        return struct.unpack('>i', self.read_bytes(4))[0]
    
    def read_int64(self) -> int:
        return struct.unpack('>q', self.read_bytes(8))[0]
    
    def read_float32(self) -> float:
        return struct.unpack('>f', self.read_bytes(4))[0]
    
    def read_float64(self) -> float:
        return struct.unpack('>d', self.read_bytes(8))[0]
    
    def read_string(self, length: int) -> str:
        return self.read_bytes(length).decode('utf-8')
    
    def decode_value(self) -> Any:
        """解码单个MessagePack值"""
        if self.pos >= self.length:
            raise ValueError("Unexpected end of data")
            
        format_byte = self.read_byte()
        
        # Positive fixint (0xxxxxxx)
        if format_byte <= 0x7f:
            return format_byte
        
        # Fixmap (1000xxxx)
        elif 0x80 <= format_byte <= 0x8f:
            size = format_byte & 0x0f
            return self.decode_map(size)
        
        # Fixarray (1001xxxx)
        elif 0x90 <= format_byte <= 0x9f:
            size = format_byte & 0x0f
            return self.decode_array(size)
        
        # Fixstr (101xxxxx)
        elif 0xa0 <= format_byte <= 0xbf:
            size = format_byte & 0x1f
            return self.read_string(size)
        
        # nil
        elif format_byte == 0xc0:
            return None
        
        # false
        elif format_byte == 0xc2:
            return False
        
        # true
        elif format_byte == 0xc3:
            return True
        
        # bin 8
        elif format_byte == 0xc4:
            size = self.read_uint8()
            return self.read_bytes(size)
        
        # bin 16
        elif format_byte == 0xc5:
            size = self.read_uint16()
            return self.read_bytes(size)
        
        # bin 32
        elif format_byte == 0xc6:
            size = self.read_uint32()
            return self.read_bytes(size)
        
        # float 32
        elif format_byte == 0xca:
            return self.read_float32()
        
        # float 64
        elif format_byte == 0xcb:
            return self.read_float64()
        
        # uint 8
        elif format_byte == 0xcc:
            return self.read_uint8()
        
        # uint 16
        elif format_byte == 0xcd:
            return self.read_uint16()
        
        # uint 32
        elif format_byte == 0xce:
            return self.read_uint32()
        
        # uint 64
        elif format_byte == 0xcf:
            return self.read_uint64()
        
        # int 8
        elif format_byte == 0xd0:
            return self.read_int8()
        
        # int 16
        elif format_byte == 0xd1:
            return self.read_int16()
        
        # int 32
        elif format_byte == 0xd2:
            return self.read_int32()
        
        # int 64
        elif format_byte == 0xd3:
            return self.read_int64()
        
        # str 8
        elif format_byte == 0xd9:
            size = self.read_uint8()
            return self.read_string(size)
        
        # str 16
        elif format_byte == 0xda:
            size = self.read_uint16()
            return self.read_string(size)
        
        # str 32
        elif format_byte == 0xdb:
            size = self.read_uint32()
            return self.read_string(size)
        
        # array 16
        elif format_byte == 0xdc:
            size = self.read_uint16()
            return self.decode_array(size)
        
        # array 32
        elif format_byte == 0xdd:
            size = self.read_uint32()
            return self.decode_array(size)
        
        # map 16
        elif format_byte == 0xde:
            size = self.read_uint16()
            return self.decode_map(size)
        
        # map 32
        elif format_byte == 0xdf:
            size = self.read_uint32()
            return self.decode_map(size)
        
        # Negative fixint (111xxxxx)
        elif format_byte >= 0xe0:
            return format_byte - 256  # Convert to signed
        
        else:
            raise ValueError(f"Unknown format byte: 0x{format_byte:02x}")
    
    def decode_array(self, size: int) -> List[Any]:
        """解码数组"""
        result = []
        for _ in range(size):
            result.append(self.decode_value())
        return result
    
    def decode_map(self, size: int) -> Dict[Any, Any]:
        """解码映射"""
        result = {}
        for _ in range(size):
            key = self.decode_value()
            value = self.decode_value()
            result[key] = value
        return result
    
    def decode(self) -> Any:
        """解码MessagePack数据"""
        try:
            return self.decode_value()
        except Exception as e:
            # 如果解码失败，返回原始数据的base64编码
            return base64.b64encode(self.data).decode('utf-8')


def decrypt(data: str) -> str:
    """解密函数的Python实现"""
    try:
        # 1. Base64解码
        # 清理非base64字符
        cleaned_data = ''.join(c for c in data if c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
        
        # 添加padding如果需要
        while len(cleaned_data) % 4 != 0:
            cleaned_data += '='
        
        try:
            decoded_bytes = base64.b64decode(cleaned_data)
        except Exception as e:
            # 如果base64解码失败，尝试其他方法
            return json.dumps({"error": f"Base64 decode failed: {str(e)}", "raw_data": data})
        
        # 2. 尝试MessagePack解码
        try:
            decoder = MessagePackDecoder(decoded_bytes)
            result = decoder.decode()
            
            # 3. 转换为JSON字符串
            def json_serializer(obj):
                """自定义JSON序列化器"""
                if isinstance(obj, bytes):
                    try:
                        return obj.decode('utf-8')
                    except:
                        return base64.b64encode(obj).decode('utf-8')
                elif hasattr(obj, '__dict__'):
                    return obj.__dict__
                else:
                    return str(obj)
            
            return json.dumps(result, ensure_ascii=False, default=json_serializer)
            
        except Exception as e:
            # 如果MessagePack解码失败，尝试直接解析为字符串
            try:
                text_result = decoded_bytes.decode('utf-8')
                return json.dumps({"text": text_result})
            except:
                # 最后的备选方案：返回十六进制表示
                hex_result = decoded_bytes.hex()
                return json.dumps({"hex": hex_result, "error": f"Decode failed: {str(e)}"})
                
    except Exception as e:
        return json.dumps({"error": f"Decrypt failed: {str(e)}", "raw_data": data})
