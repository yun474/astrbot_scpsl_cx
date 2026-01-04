from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import socket
import struct
import asyncio
import time
from typing import Dict, Any, Optional
import os
from datetime import datetime
import re  # 新增：用于IP地址验证

@register("scpsl_server_query", "若梦", "SCP:SL服务器查询插件，支持配置预设服务器", "1.2.0")
class SCPSLServerQuery(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config  # 接收配置
        self.default_port = 7777
        self.timeout = 5

        
        # 确保配置中有servers字段
        if "servers" not in self.config:
            self.config["servers"] = [
                {"name": "示例服务器", "ip": "127.0.0.1", "port": 7777}
            ]
            self.config.save_config()  # 保存默认配置
    
    @filter.command("cx")
    async def query_server_status(self, event: AstrMessageEvent):
        """查询SCP:SL服务器在线人数和状态
        支持两种查询方式:
        1. /cx <服务器名称> - 查询预设服务器
        2. /cx <IP地址> [端口] - 查询自定义服务器
        
        服务器管理命令:
        1. /cx add <名称> <IP> [端口] - 添加预设服务器
        2. /cx edit <序号> <名称> <IP> [端口] - 编辑预设服务器
        3. /cx delete <序号> - 删除预设服务器
        4. /cx list - 显示所有预设服务器
        """
        message_parts = event.message_str.strip().split()
        
        if len(message_parts) < 2:
            # 显示帮助信息
            help_msg = "🎮 SCP:SL服务器查询助手\n\n"
            help_msg += "查询命令:\n"
            help_msg += "1. /cx <服务器名称> - 查询预设服务器\n"
            help_msg += "2. /cx <IP地址> [端口] - 查询自定义服务器\n\n"
            help_msg += "管理命令:\n"
            help_msg += "1. /cx add <名称> <IP> [端口] - 添加预设服务器\n"
            help_msg += "2. /cx edit <序号> <名称> <IP> [端口] - 编辑预设服务器\n"
            help_msg += "3. /cx delete <序号> - 删除预设服务器\n"
            help_msg += "4. /cx list - 显示所有预设服务器"
            yield event.plain_result(help_msg)
            return
            
        command = message_parts[1].lower()
        
        # 处理服务器列表显示
        if command == "list":
            server_list = "🎮 预设服务器列表:\n"
            for i, server in enumerate(self.config["servers"], 1):
                server_list += f"{i}. {server['name']} - {server['ip']}:{server['port']}\n"
            yield event.plain_result(server_list)
            return
        
        # 处理添加服务器
        if command == "add":
            if len(message_parts) < 4:
                yield event.plain_result("❌ 格式错误！正确格式: /cx add <名称> <IP> [端口]")
                return
                
            name = message_parts[2]
            ip = message_parts[3]
            port = int(message_parts[4]) if len(message_parts) > 4 else self.default_port
            
            # 验证IP地址
            if not self._is_valid_ip(ip):
                yield event.plain_result("❌ 无效的IP地址！")
                return
                
            # 验证端口
            if not (1 <= port <= 65535):
                yield event.plain_result("❌ 端口号必须在1-65535之间！")
                return
                
            # 检查名称是否已存在
            if any(s["name"] == name for s in self.config["servers"]):
                yield event.plain_result(f"❌ 已存在同名服务器: {name}")
                return
                
            # 添加服务器
            self.config["servers"].append({
                "name": name,
                "ip": ip,
                "port": port
            })
            self.config.save_config()
            yield event.plain_result(f"✅ 已添加服务器: {name} ({ip}:{port})")
            return
        
        # 处理编辑服务器
        if command == "edit":
            if len(message_parts) < 5:
                yield event.plain_result("❌ 格式错误！正确格式: /cx edit <序号> <名称> <IP> [端口]")
                return
                
            try:
                index = int(message_parts[2]) - 1  # 转换为0基索引
                if index < 0 or index >= len(self.config["servers"]):
                    yield event.plain_result("❌ 序号不存在！使用 /cx list 查看所有服务器")
                    return
            except ValueError:
                yield event.plain_result("❌ 序号必须是数字！")
                return
                
            name = message_parts[3]
            ip = message_parts[4]
            port = int(message_parts[5]) if len(message_parts) > 5 else self.default_port
            
            # 验证IP地址
            if not self._is_valid_ip(ip):
                yield event.plain_result("❌ 无效的IP地址！")
                return
                
            # 验证端口
            if not (1 <= port <= 65535):
                yield event.plain_result("❌ 端口号必须在1-65535之间！")
                return
                
            # 检查名称是否与其他服务器冲突
            if any(s["name"] == name and s != self.config["servers"][index] for s in self.config["servers"]):
                yield event.plain_result(f"❌ 已存在同名服务器: {name}")
                return
                
            # 更新服务器信息
            self.config["servers"][index] = {
                "name": name,
                "ip": ip,
                "port": port
            }
            self.config.save_config()
            yield event.plain_result(f"✅ 已更新服务器 #{index+1}: {name} ({ip}:{port})")
            return
        
        # 处理删除服务器
        if command == "delete":
            if len(message_parts) < 3:
                yield event.plain_result("❌ 格式错误！正确格式: /cx delete <序号>")
                return
                
            try:
                index = int(message_parts[2]) - 1  # 转换为0基索引
                if index < 0 or index >= len(self.config["servers"]):
                    yield event.plain_result("❌ 序号不存在！使用 /cx list 查看所有服务器")
                    return
            except ValueError:
                yield event.plain_result("❌ 序号必须是数字！")
                return
                
            # 删除服务器
            deleted = self.config["servers"].pop(index)
            self.config.save_config()
            yield event.plain_result(f"✅ 已删除服务器: {deleted['name']} ({deleted['ip']}:{deleted['port']})")
            return
        
        # 原有查询逻辑
        query_param = message_parts[1]
        
        # 先尝试匹配预设服务器
        matched_servers = [s for s in self.config["servers"] if query_param in s["name"]]
        
        if matched_servers:
            # 如果找到多个匹配的服务器，全部查询
            response = "🎮 服务器状态查询结果\n\n"
            for server in matched_servers:
                try:
                    server_info = await self.query_scpsl_server(server["ip"], server["port"])
                    if server_info:
                        response += f"[{server['name']}]\n"
                        response += f"📍 服务器: {server['ip']}:{server['port']}\n"
                        response += f"👥 在线人数: {server_info.get('players', 'N/A')}/{server_info.get('max_players', 'N/A')}\n"
                        response += f"🏷️ 服务器名: {server_info.get('name', 'Unknown')}\n"
                        response += f"🎯 游戏模式: {server_info.get('gamemode', 'Unknown')}\n"
                        response += f"🗺️ 地图: {server_info.get('map', 'Unknown')}\n"
                        response += f"⏱️ 回合时间: {server_info.get('round_time', 'N/A')}\n"
                        response += f"🔄 状态: {'🟢 在线' if server_info.get('online') else '🔴 离线'}\n\n"
                    else:
                        response += f"[{server['name']}] {server['ip']}:{server['port']} 无法连接\n\n"
                except Exception as e:
                    logger.error(f"查询服务器 {server['name']} 时出错: {e}")
                    response += f"[{server['name']}] 查询失败: {str(e)}\n\n"
            yield event.plain_result(response)
            return
        
        # 如果不是预设服务器，则按IP:端口处理
        server_ip = query_param
        
        # 解析端口参数
        if len(message_parts) > 2:
            try:
                port_str = message_parts[2].strip('[]')
                server_port = int(port_str)
                if not (1 <= server_port <= 65535):
                    yield event.plain_result("❌ 端口号必须在1-65535之间！")
                    return
            except ValueError:
                yield event.plain_result(f"❌ 无效的端口号: {message_parts[2]}\n端口号必须是数字！")
                return
        else:
            server_port = self.default_port
        
        try:
            server_info = await self.query_scpsl_server(server_ip, server_port)
            if server_info:
                response = f"🎮 SCP:SL 服务器状态\n"
                response += f"📍 服务器: {server_ip}:{server_port}\n"
                response += f"👥 在线人数: {server_info.get('players', 'N/A')}/{server_info.get('max_players', 'N/A')}\n"
                response += f"🏷️ 服务器名: {server_info.get('name', 'Unknown')}\n"
                response += f"🎯 游戏模式: {server_info.get('gamemode', 'Unknown')}\n"
                response += f"🗺️ 地图: {server_info.get('map', 'Unknown')}\n"
                response += f"⏱️ 回合时间: {server_info.get('round_time', 'N/A')}\n"
                response += f"🔄 状态: {'🟢 在线' if server_info.get('online') else '🔴 离线'}"
                yield event.plain_result(response)
            else:
                yield event.plain_result(f"❌ 无法连接到服务器 {server_ip}:{server_port}\n请检查IP地址和端口是否正确！")
        except Exception as e:
            logger.error(f"查询服务器时出错: {e}")
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
    
    # 新增：IP地址验证方法
    def _is_valid_ip(self, ip: str) -> bool:
        """验证IPv4地址格式"""
        pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(pattern, ip)
        if not match:
            return False
        # 验证每个段的数值范围
        for part in match.groups():
            if not (0 <= int(part) <= 255):
                return False
        return True
    
    # 以下为原有方法，保持不变
    async def _query_server_tcp(self, ip: str, port: int) -> Dict[str, Any]:
        """使用支持challenge的A2S协议查询服务器信息"""
        query_ports = [port, port + 1, port - 1]
        
        for query_port in query_ports:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5.0)
                
                start_time = time.time()
                
                # 第一次A2S_INFO查询
                query = b"\xFF\xFF\xFF\xFF\x54Source Engine Query\x00"
                sock.sendto(query, (ip, query_port))
                
                response, addr = sock.recvfrom(1400)
                
                if len(response) < 5 or response[:4] != b"\xFF\xFF\xFF\xFF":
                    continue
                
                # 处理challenge响应
                if response[4] == 0x41:  # S2C_CHALLENGE
                    if len(response) >= 9:
                        challenge = struct.unpack('<I', response[5:9])[0]
                        query_with_challenge = query + struct.pack('<I', challenge)
                        sock.sendto(query_with_challenge, (ip, query_port))
                        response, addr = sock.recvfrom(1400)
                    else:
                        continue
                
                ping = round((time.time() - start_time) * 1000)
                
                # 解析A2S_INFO响应
                if len(response) >= 5 and response[4] == 0x49:  # A2S_INFO response
                    result = self._parse_a2s_info(response[5:], ping)
                    if result.get('status') == 'online':
                        return result
                
            except socket.timeout:
                logger.debug(f"查询超时: {ip}:{query_port}")
                continue
            except ConnectionRefusedError:
                logger.debug(f"连接被拒绝: {ip}:{query_port}")
                continue
            except Exception as e:
                logger.debug(f"查询异常 {ip}:{query_port}: {str(e)}")
                continue
            finally:
                if sock:
                    try:
                        sock.close()
                    except:
                        pass
        
        return {'status': 'offline', 'error': '无法连接到服务器'}
    
    def _parse_a2s_info(self, data: bytes, ping: int) -> Dict[str, Any]:
         """解析A2S_INFO响应数据"""
         try:
             offset = 0
             
             # 协议版本
             protocol = data[offset]
             offset += 1
             
             # 服务器名称
             server_name_end = data.find(b'\x00', offset)
             server_name = data[offset:server_name_end].decode('utf-8', errors='ignore')
             offset = server_name_end + 1
             
             # 地图名称
             map_name_end = data.find(b'\x00', offset)
             map_name = data[offset:map_name_end].decode('utf-8', errors='ignore')
             offset = map_name_end + 1
             
             # 文件夹名称
             folder_end = data.find(b'\x00', offset)
             folder = data[offset:folder_end].decode('utf-8', errors='ignore')
             offset = folder_end + 1
             
             # 游戏名称
             game_end = data.find(b'\x00', offset)
             game = data[offset:game_end].decode('utf-8', errors='ignore')
             offset = game_end + 1
             
             # 应用ID
             if offset + 2 <= len(data):
                 app_id = struct.unpack('<H', data[offset:offset+2])[0]
                 offset += 2
             else:
                 app_id = 0
             
             # 玩家数量
             if offset < len(data):
                 players = data[offset]
                 offset += 1
             else:
                 players = 0
             
             # 最大玩家数
             if offset < len(data):
                 max_players = data[offset]
                 offset += 1
             else:
                 max_players = 20
             
             # 机器人数量
             if offset < len(data):
                 bots = data[offset]
                 offset += 1
             else:
                 bots = 0
             
             # 服务器类型
             if offset < len(data):
                 server_type = chr(data[offset])
                 offset += 1
             else:
                 server_type = 'd'
             
             # 平台
             if offset < len(data):
                 platform = chr(data[offset])
                 offset += 1
             else:
                 platform = 'l'
             
             # 是否需要密码
             if offset < len(data):
                 password = bool(data[offset])
                 offset += 1
             else:
                 password = False
             
             # VAC状态
             if offset < len(data):
                 vac = bool(data[offset])
                 offset += 1
             else:
                 vac = False
             
             return {
                 'status': 'online',
                 'players': players,
                 'max_players': max_players,
                 'server_name': server_name,
                 'map': map_name,
                 'game_mode': game if game else '未知模式',
                 'round_time': '未知',
                 'ping': ping,
                 'bots': bots,
                 'password': password,
                 'vac': vac
             }
             
         except Exception as e:
             return {
                 'status': 'error',
                 'error': f'解析A2S响应失败: {str(e)}'
             }
     
    async def query_scpsl_server(self, ip: str, port: int) -> dict:
        """查询SCP:SL服务器信息（使用A2S协议）"""
        result = await self._query_server_tcp(ip, port)
        
        if result and result.get('status') == 'online':
            return {
                'online': True,
                'ping': result.get('ping', 0),
                'players': result.get('players', 0),
                'max_players': result.get('max_players', 20),
                'name': result.get('server_name', 'SCP:SL Server'),
                'gamemode': result.get('game_mode', 'Classic'),
                'map': result.get('map', 'Facility'),
                'round_time': result.get('round_time', '00:00'),
                'version': 'Unknown'
            }
        else:
            return None
    
    async def query_scpsl_server_udp(self, ip: str, port: int) -> dict:
        """UDP查询服务器信息（使用A2S协议）"""
        return await self._query_server_tcp(ip, port)
