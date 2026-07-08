#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChatX - Terminal Encrypted LAN Chat
Requires: pip install cryptography windows-curses
"""

import socket
import threading
import json
import time
import uuid
import os
import sys
import base64
from datetime import datetime
from cryptography.fernet import Fernet

try:
    import curses
except ImportError:
    os.system(f"{sys.executable} -m pip install windows-curses")
    import curses

class ChatX:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.running = True
        self.username = ""
        self.current_room = None
        self.joined_rooms = {}
        self.rooms = {}
        self.messages = {}
        self.encryption_keys = {}
        self.hosted_rooms = {}
        self.client_connections = {}
        self.room_sockets = {}
        self.unread = {}
        self.file_transfers = {}
        self.server_sockets = {}  # 保存服务器socket用于关闭
        
        self.BROADCAST_PORT = 50000
        self.CHAT_PORT_RANGE = (50001, 50100)
        self.running_threads = True
        
        self.screen_mode = 'login'
        self.selected_idx = 0
        self.input_buffer = ""
        self.cursor_pos = 0
        self.chat_scroll = 0
        self.auth_input = ""
        self.selected_room_info = None
        self.auth_type = None
        
        self.term_h, self.term_w = 0, 0
        self.update_size()
        
        self.init_colors()
        self.start_network()
        self.main_loop()

    def init_colors(self):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)    # header
        curses.init_pair(2, curses.COLOR_GREEN, -1)                   # self msg
        curses.init_pair(3, curses.COLOR_CYAN, -1)                    # other msg
        curses.init_pair(4, curses.COLOR_YELLOW, -1)                  # system
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_WHITE)   # selected
        curses.init_pair(6, curses.COLOR_WHITE, -1)                   # normal

    def update_size(self):
        self.term_h, self.term_w = self.stdscr.getmaxyx()

    def start_network(self):
        self.broadcast_thread = threading.Thread(target=self.listen_broadcasts, daemon=True)
        self.broadcast_thread.start()

    def listen_broadcasts(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('', self.BROADCAST_PORT))
        except:
            pass
        sock.settimeout(1)
        
        while self.running_threads:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode())
                if msg.get('type') == 'room_announce':
                    rid = msg['room_id']
                    self.rooms[rid] = {
                        'name': msg['name'],
                        'host': msg['host'],
                        'ip': addr[0],
                        'port': msg['port'],
                        'auth_type': msg.get('auth_type', 'open'),
                        'chat_type': msg.get('chat_type', 'group'),
                        'members': msg.get('member_count', 0),
                        'last_seen': time.time()
                    }
            except socket.timeout:
                continue
            except:
                continue
        sock.close()

    def main_loop(self):
        self.stdscr.keypad(True)
        self.stdscr.nodelay(False)
        
        while self.running:
            self.update_size()
            self.stdscr.erase()
            self.draw()
            self.stdscr.refresh()
            
            try:
                key = self.stdscr.getch()
            except:
                continue
            
            if key == curses.KEY_RESIZE:
                self.update_size()
                continue
            
            self.handle_input(key)

    def draw(self):
        h, w = self.term_h, self.term_w
        if self.screen_mode == 'login':
            self.draw_login(h, w)
        elif self.screen_mode == 'rooms':
            self.draw_rooms(h, w)
        elif self.screen_mode == 'chat':
            self.draw_chat(h, w)
        elif self.screen_mode == 'join_auth':
            self.draw_join_auth(h, w)

    def draw_header(self, y, w):
        title = " ChatX v1.0 "
        self.stdscr.addstr(y, 0, " " * (w - 1), curses.color_pair(1))
        self.stdscr.addstr(y, (w - len(title)) // 2, title, curses.color_pair(1) | curses.A_BOLD)

    def draw_login(self, h, w):
        cy = max(2, h // 2 - 3)
        self.draw_header(0, w)
        
        self.stdscr.addstr(cy, (w - 20) // 2, "=== ChatX ===", curses.A_BOLD)
        self.stdscr.addstr(cy + 2, (w - 30) // 2, "Enter your username:", curses.color_pair(6))
        self.stdscr.addstr(cy + 4, (w - 30) // 2, "> " + self.input_buffer, curses.color_pair(2) | curses.A_BOLD)
        self.stdscr.addstr(cy + 4, (w - 30) // 2 + 2 + self.cursor_pos, " ", curses.A_REVERSE)
        
        curses.curs_set(1)
        self.stdscr.move(cy + 4, (w - 30) // 2 + 2 + self.cursor_pos)
        
        self.draw_bottom(h, w, " Enter to confirm ")

    def draw_rooms(self, h, w):
        y = 1
        self.draw_header(0, w)
        y += 1
        
        # Clean expired rooms
        now = time.time()
        for rid in list(self.rooms.keys()):
            if now - self.rooms[rid].get('last_seen', 0) > 15:
                del self.rooms[rid]
        
        # My rooms
        if self.joined_rooms:
            self.stdscr.addstr(y, 2, "=== My Rooms ===", curses.A_BOLD)
            y += 1
            for rid, info in list(self.joined_rooms.items())[:6]:
                mark = "> " if rid == self.current_room else "  "
                icon = "(P)" if info.get('type') == 'private' else "(G)"
                unread = self.unread.get(rid, 0)
                unread_str = f" [{unread}]" if unread > 0 else ""
                self.stdscr.addstr(y, 2, f"{mark}{icon} {info['name']}{unread_str}"[:w-3], curses.color_pair(2))
                y += 1
            y += 1
        
        # Available rooms
        self.stdscr.addstr(y, 2, "=== Available ===", curses.A_BOLD)
        y += 1
        
        room_list = list(self.rooms.values())
        max_show = max(0, h - y - 3)
        
        for i, info in enumerate(room_list[:max_show]):
            attr = curses.color_pair(5) | curses.A_BOLD if i == self.selected_idx else curses.color_pair(6)
            auth = {'open': '[ ]', 'password': '[#]', 'key': '[*]'}.get(info['auth_type'], '[?]')
            line = f" {auth}(G) {info['name'][:25]} ({info['members']}) - {info['host']}"
            self.stdscr.addstr(y, 2, line[:w-4], attr)
            y += 1
        
        if not self.rooms:
            self.stdscr.addstr(y, 2, "(listening for rooms...)", curses.A_DIM)
        
        curses.curs_set(0)
        self.draw_bottom(h, w, f" {self.username} | Up/Down | Enter Join | N New | Q Quit ")

    def draw_chat(self, h, w):
        y = 1
        self.draw_header(0, w)
        y += 1
        
        room_id = self.current_room
        chat_h = max(1, h - y - 5)
        
        if room_id and room_id in self.messages:
            msgs = self.messages[room_id]
            start = max(0, len(msgs) - chat_h - self.chat_scroll)
            
            for msg in msgs[start:start + chat_h]:
                ts = msg.get('timestamp', '--:--')
                sender = msg.get('sender', '')
                content = msg.get('content', '')
                
                if msg.get('type') == 'system':
                    self.stdscr.addstr(y, 0, f" [{ts}]".ljust(9), curses.A_DIM)
                    self.stdscr.addstr(y, 9, content[:w-10], curses.color_pair(4))
                else:
                    self.stdscr.addstr(y, 0, f" [{ts}]".ljust(9), curses.A_DIM)
                    color = curses.color_pair(2) | curses.A_BOLD if sender == self.username else curses.color_pair(3)
                    self.stdscr.addstr(y, 9, f"<{sender}> {content}"[:w-10], color)
                y += 1
                if y >= h - 5:
                    break
        
        # Input line
        input_y = h - 4
        prompt = f" [{self.username[:8]}]> "
        self.stdscr.addstr(input_y, 0, prompt, curses.color_pair(2) | curses.A_BOLD)
        self.stdscr.addstr(input_y, len(prompt), self.input_buffer[:w-len(prompt)-1])
        
        # Cursor
        cursor_x = len(prompt) + self.cursor_pos
        if cursor_x < w - 1 and input_y < h:
            curses.curs_set(1)
            self.stdscr.move(input_y, cursor_x)
        else:
            curses.curs_set(0)
        
        # Status
        room = self.joined_rooms.get(room_id, {})
        self.draw_bottom(h, w, f" {room.get('name','?')} | {len(room.get('members',[]))} members | Esc Back | PgUp/PgDn Scroll ")

    def draw_join_auth(self, h, w):
        y = 1
        self.draw_header(0, w)
        y += 2
        
        if self.selected_room_info:
            info = self.selected_room_info
            self.stdscr.addstr(y, 2, f"Join: {info['name']}", curses.A_BOLD)
            y += 2
            self.stdscr.addstr(y, 2, f"Host: {info['host']}", curses.color_pair(6))
            y += 1
            self.stdscr.addstr(y, 2, f"Members: {info['members']}", curses.color_pair(6))
            y += 2
            
            auth = info.get('auth_type', 'open')
            if auth == 'open':
                self.stdscr.addstr(y, 2, "Open room - press Enter to join", curses.color_pair(2))
            else:
                label = "Password:" if auth == 'password' else "Key (XXXX-XXXX-XXXX-XXXX-XXXX):"
                self.stdscr.addstr(y, 2, label, curses.color_pair(4))
                self.stdscr.addstr(y + 2, 2, "> " + self.auth_input, curses.color_pair(2))
                self.stdscr.addstr(y + 2, 4 + len(self.auth_input), " ", curses.A_REVERSE)
                curses.curs_set(1)
                self.stdscr.move(y + 2, 4 + len(self.auth_input))
        
        self.draw_bottom(h, w, " Enter Join | Esc Cancel ")

    def draw_bottom(self, h, w, text):
        if h >= 2:
            try:
                self.stdscr.addstr(h-2, 0, "─" * (w-1), curses.color_pair(1))
                self.stdscr.addstr(h-1, 0, text[:w-1].ljust(w-1), curses.color_pair(1) | curses.A_BOLD)
            except:
                pass

    def handle_input(self, key):
        if self.screen_mode == 'login':
            self.handle_login_input(key)
        elif self.screen_mode == 'rooms':
            self.handle_rooms_input(key)
        elif self.screen_mode == 'chat':
            self.handle_chat_input(key)
        elif self.screen_mode == 'join_auth':
            self.handle_auth_input(key)

    def handle_login_input(self, key):
        if key in (ord('\n'), ord('\r'), 10, curses.KEY_ENTER):
            self.username = self.input_buffer.strip() or f"User_{str(uuid.uuid4())[:6]}"
            self.input_buffer = ""
            self.cursor_pos = 0
            self.screen_mode = 'rooms'
        elif key in (curses.KEY_BACKSPACE, 127, 8, ord('\b')):
            if self.cursor_pos > 0:
                self.input_buffer = self.input_buffer[:self.cursor_pos-1] + self.input_buffer[self.cursor_pos:]
                self.cursor_pos -= 1
        elif key == curses.KEY_DC:  # Delete key
            if self.cursor_pos < len(self.input_buffer):
                self.input_buffer = self.input_buffer[:self.cursor_pos] + self.input_buffer[self.cursor_pos+1:]
        elif key == curses.KEY_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
        elif key == curses.KEY_RIGHT:
            self.cursor_pos = min(len(self.input_buffer), self.cursor_pos + 1)
        elif key == curses.KEY_HOME:
            self.cursor_pos = 0
        elif key == curses.KEY_END:
            self.cursor_pos = len(self.input_buffer)
        elif 32 <= key <= 126:
            c = chr(key)
            self.input_buffer = self.input_buffer[:self.cursor_pos] + c + self.input_buffer[self.cursor_pos:]
            self.cursor_pos += 1

    def handle_rooms_input(self, key):
        room_list = list(self.rooms.values())
        
        if key == curses.KEY_UP:
            self.selected_idx = max(0, self.selected_idx - 1)
        elif key == curses.KEY_DOWN:
            self.selected_idx = min(len(room_list)-1, self.selected_idx + 1) if room_list else 0
        elif key in (ord('\n'), ord('\r'), 10, curses.KEY_ENTER):
            if room_list and self.selected_idx < len(room_list):
                info = room_list[self.selected_idx]
                self.selected_room_info = info
                if info.get('auth_type') == 'open':
                    self.join_room(info, 'none', '')
                else:
                    self.screen_mode = 'join_auth'
                    self.auth_input = ""
                    self.auth_type = info.get('auth_type')
        elif key in (ord('n'), ord('N')):
            self.create_room()
        elif key in (ord('q'), ord('Q')):
            self.quit_program()
        elif key == 27:
            if self.current_room:
                self.leave_current_room()

    def handle_chat_input(self, key):
        if key == 27:  # Esc
            self.input_buffer = ""
            self.cursor_pos = 0
            self.screen_mode = 'rooms'
        elif key == curses.KEY_PPAGE:
            self.chat_scroll += 5
        elif key == curses.KEY_NPAGE:
            self.chat_scroll = max(0, self.chat_scroll - 5)
        elif key in (ord('\n'), ord('\r'), 10, curses.KEY_ENTER):
            if self.input_buffer.strip():
                if self.input_buffer.startswith('/file '):
                    self.send_file(self.input_buffer[6:].strip())
                else:
                    self.send_message(self.input_buffer.strip())
            self.input_buffer = ""
            self.cursor_pos = 0
        elif key in (curses.KEY_BACKSPACE, 127, 8, ord('\b')):
            if self.cursor_pos > 0:
                self.input_buffer = self.input_buffer[:self.cursor_pos-1] + self.input_buffer[self.cursor_pos:]
                self.cursor_pos -= 1
        elif key == curses.KEY_DC:
            if self.cursor_pos < len(self.input_buffer):
                self.input_buffer = self.input_buffer[:self.cursor_pos] + self.input_buffer[self.cursor_pos+1:]
        elif key == curses.KEY_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
        elif key == curses.KEY_RIGHT:
            self.cursor_pos = min(len(self.input_buffer), self.cursor_pos + 1)
        elif key == curses.KEY_HOME:
            self.cursor_pos = 0
        elif key == curses.KEY_END:
            self.cursor_pos = len(self.input_buffer)
        elif 32 <= key <= 126:
            c = chr(key)
            self.input_buffer = self.input_buffer[:self.cursor_pos] + c + self.input_buffer[self.cursor_pos:]
            self.cursor_pos += 1

    def handle_auth_input(self, key):
        if key == 27:
            self.screen_mode = 'rooms'
            self.auth_input = ""
        elif key in (ord('\n'), ord('\r'), 10, curses.KEY_ENTER):
            if self.selected_room_info:
                self.join_room(self.selected_room_info, self.auth_type, self.auth_input)
        elif key in (curses.KEY_BACKSPACE, 127, 8, ord('\b')):
            self.auth_input = self.auth_input[:-1]
        elif key == curses.KEY_DC:
            pass
        elif 32 <= key <= 126:
            self.auth_input += chr(key)

    def join_room(self, room_info, auth_method, auth_value):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((room_info['ip'], room_info['port']))
            
            auth_msg = {'type': 'auth', 'method': auth_method, 'value': auth_value, 'username': self.username}
            sock.send(json.dumps(auth_msg).encode())
            
            response = json.loads(sock.recv(1024).decode())
            
            if response.get('status') == 'success':
                room_id = str(uuid.uuid4())
                
                self.joined_rooms[room_id] = {
                    'name': room_info['name'],
                    'type': room_info.get('chat_type', 'group'),
                    'host': room_info['host'],
                    'members': [self.username, room_info['host']]
                }
                
                if 'encryption_key' in response:
                    self.encryption_keys[room_id] = base64.urlsafe_b64decode(response['encryption_key'])
                
                self.room_sockets[room_id] = sock
                self.messages[room_id] = [{'type': 'system', 'content': f"Joined: {room_info['name']}", 'timestamp': datetime.now().strftime('%H:%M')}]
                self.current_room = room_id
                self.screen_mode = 'chat'
                self.auth_input = ""
                self.chat_scroll = 0
                
                threading.Thread(target=self.receive_messages, args=(sock, room_id), daemon=True).start()
            else:
                self.screen_mode = 'rooms'
                self.auth_input = ""
        except:
            self.screen_mode = 'rooms'
            self.auth_input = ""

    def create_room(self):
        room_id = str(uuid.uuid4())
        port = self.find_port()
        if not port:
            return
        
        room_info = {
            'room_id': room_id,
            'name': f"{self.username}'s room",
            'port': port,
            'host': self.username,
            'auth_type': 'open',
            'chat_type': 'group',
            'members': 1
        }
        
        self.hosted_rooms[room_id] = room_info
        self.encryption_keys[room_id] = Fernet.generate_key()
        self.joined_rooms[room_id] = {
            'name': room_info['name'],
            'type': 'group',
            'host': self.username,
            'members': [self.username]
        }
        self.messages[room_id] = [{'type': 'system', 'content': f"Room created", 'timestamp': datetime.now().strftime('%H:%M')}]
        self.current_room = room_id
        self.screen_mode = 'chat'
        self.chat_scroll = 0
        
        self.start_server(room_id, port)
        threading.Thread(target=self.broadcast_room, args=(room_info,), daemon=True).start()

    def find_port(self):
        for port in range(self.CHAT_PORT_RANGE[0], self.CHAT_PORT_RANGE[1] + 1):
            try:
                s = socket.socket()
                s.bind(('', port))
                s.close()
                return port
            except:
                continue
        return None

    def start_server(self, room_id, port):
        ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ss.bind(('', port))
        ss.listen(5)
        self.server_sockets[room_id] = ss
        self.client_connections[room_id] = {}
        
        def accept():
            while self.running_threads and room_id in self.hosted_rooms:
                try:
                    ss.settimeout(1)
                    cs, addr = ss.accept()
                    threading.Thread(target=self.handle_client, args=(cs, addr, room_id), daemon=True).start()
                except socket.timeout:
                    continue
                except:
                    break
        
        threading.Thread(target=accept, daemon=True).start()

    def handle_client(self, cs, addr, room_id):
        try:
            data = cs.recv(1024).decode()
            auth = json.loads(data)
            
            response = {
                'status': 'success',
                'encryption_key': base64.urlsafe_b64encode(self.encryption_keys[room_id]).decode()
            }
            cs.send(json.dumps(response).encode())
            
            cid = f"{addr[0]}:{addr[1]}"
            username = auth.get('username', '?')
            self.client_connections[room_id][cid] = {'socket': cs, 'username': username}
            
            # Add member
            if room_id in self.joined_rooms and username not in self.joined_rooms[room_id]['members']:
                self.joined_rooms[room_id]['members'].append(username)
            
            if room_id in self.messages:
                self.messages[room_id].append({'type': 'system', 'content': f"{username} joined", 'timestamp': datetime.now().strftime('%H:%M')})
            
            while self.running_threads:
                data = cs.recv(8192)
                if not data:
                    break
                
                if room_id in self.encryption_keys:
                    f = Fernet(self.encryption_keys[room_id])
                    msg = json.loads(f.decrypt(data).decode())
                    
                    if msg['type'] == 'chat':
                        msg['timestamp'] = datetime.now().strftime('%H:%M')
                        if room_id in self.messages:
                            self.messages[room_id].append(msg)
                        
                        # Forward to others
                        for c in self.client_connections[room_id].values():
                            if c['socket'] != cs:
                                try:
                                    c['socket'].send(data)
                                except:
                                    pass
        except:
            pass
        finally:
            if room_id in self.client_connections and cid in self.client_connections[room_id]:
                username = self.client_connections[room_id][cid].get('username', '?')
                del self.client_connections[room_id][cid]
                if room_id in self.messages:
                    self.messages[room_id].append({'type': 'system', 'content': f"{username} left", 'timestamp': datetime.now().strftime('%H:%M')})
                if room_id in self.joined_rooms and username in self.joined_rooms[room_id]['members']:
                    self.joined_rooms[room_id]['members'].remove(username)
            cs.close()

    def broadcast_room(self, room_info):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        while self.running_threads and room_info['room_id'] in self.hosted_rooms:
            try:
                msg = json.dumps({
                    'type': 'room_announce',
                    'room_id': room_info['room_id'],
                    'name': room_info['name'],
                    'host': self.username,
                    'port': room_info['port'],
                    'auth_type': room_info.get('auth_type', 'open'),
                    'chat_type': 'group',
                    'member_count': len(self.client_connections.get(room_info['room_id'], {})) + 1
                })
                sock.sendto(msg.encode(), ('255.255.255.255', self.BROADCAST_PORT))
                time.sleep(2)
            except:
                break
        sock.close()

    def send_message(self, content):
        room_id = self.current_room
        if not room_id:
            return
        
        msg = {
            'type': 'chat',
            'sender': self.username,
            'content': content,
            'timestamp': datetime.now().strftime('%H:%M')
        }
        
        if room_id in self.messages:
            self.messages[room_id].append(msg)
        
        if room_id in self.encryption_keys:
            f = Fernet(self.encryption_keys[room_id])
            encrypted = f.encrypt(json.dumps(msg).encode())
            
            if room_id in self.client_connections:
                for c in self.client_connections[room_id].values():
                    try:
                        c['socket'].send(encrypted)
                    except:
                        pass
            elif room_id in self.room_sockets:
                try:
                    self.room_sockets[room_id].send(encrypted)
                except:
                    pass

    def send_file(self, path):
        if not os.path.exists(path):
            self.messages[self.current_room].append({'type': 'system', 'content': f"File not found: {path}", 'timestamp': datetime.now().strftime('%H:%M')})
            return
        
        filename = os.path.basename(path)
        size = os.path.getsize(path)
        
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        
        msg = {
            'type': 'file',
            'sender': self.username,
            'filename': filename,
            'size': size,
            'data': data,
            'timestamp': datetime.now().strftime('%H:%M')
        }
        
        if self.current_room in self.messages:
            self.messages[self.current_room].append({'type': 'system', 'content': f"Sent file: {filename} ({self.fmt_size(size)})", 'timestamp': datetime.now().strftime('%H:%M')})
        
        if self.current_room in self.encryption_keys:
            f = Fernet(self.encryption_keys[self.current_room])
            encrypted = f.encrypt(json.dumps(msg).encode())
            
            if self.current_room in self.client_connections:
                for c in self.client_connections[self.current_room].values():
                    try:
                        c['socket'].send(encrypted)
                    except:
                        pass
            elif self.current_room in self.room_sockets:
                try:
                    self.room_sockets[self.current_room].send(encrypted)
                except:
                    pass

    def fmt_size(self, size):
        if size < 1024:
            return f"{size}B"
        elif size < 1024*1024:
            return f"{size/1024:.1f}KB"
        else:
            return f"{size/1024/1024:.1f}MB"

    def receive_messages(self, sock, room_id):
        while self.running_threads and room_id in self.joined_rooms:
            try:
                sock.settimeout(1)
                data = sock.recv(65536)
                if not data:
                    break
                
                if room_id in self.encryption_keys:
                    f = Fernet(self.encryption_keys[room_id])
                    msg = json.loads(f.decrypt(data).decode())
                    
                    if msg['type'] == 'chat':
                        msg['encrypt_info'] = f"[{len(data)}B]"
                        if room_id in self.messages:
                            self.messages[room_id].append(msg)
                    elif msg['type'] == 'file':
                        self.save_file(msg)
            except socket.timeout:
                continue
            except:
                break

    def save_file(self, msg):
        filename = msg.get('filename', 'unknown')
        data = base64.b64decode(msg['data'])
        
        save_dir = "received_files"
        os.makedirs(save_dir, exist_ok=True)
        
        path = os.path.join(save_dir, filename)
        counter = 1
        name, ext = os.path.splitext(filename)
        while os.path.exists(path):
            path = os.path.join(save_dir, f"{name}_{counter}{ext}")
            counter += 1
        
        with open(path, 'wb') as f:
            f.write(data)
        
        if self.current_room in self.messages:
            self.messages[self.current_room].append({'type': 'system', 'content': f"Received: {os.path.basename(path)} ({self.fmt_size(len(data))})", 'timestamp': datetime.now().strftime('%H:%M')})

    def leave_current_room(self):
        if self.current_room:
            rid = self.current_room
            if rid in self.room_sockets:
                try:
                    self.room_sockets[rid].close()
                except:
                    pass
                del self.room_sockets[rid]
            if rid in self.joined_rooms:
                del self.joined_rooms[rid]
            self.current_room = None
            self.screen_mode = 'rooms'

    def quit_program(self):
        """优雅退出 - 关闭所有房间"""
        # 关闭所有服务器
        for rid, ss in list(self.server_sockets.items()):
            try:
                ss.close()
            except:
                pass
        self.server_sockets.clear()
        
        # 关闭所有客户端连接
        for rid, sock in list(self.room_sockets.items()):
            try:
                sock.close()
            except:
                pass
        self.room_sockets.clear()
        
        # 清理托管房间
        self.hosted_rooms.clear()
        self.client_connections.clear()
        
        self.running_threads = False
        self.running = False

    def on_close(self):
        self.quit_program()


def main(stdscr):
    app = ChatX(stdscr)

if __name__ == "__main__":
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print("Installing dependencies...")
        os.system(f"{sys.executable} -m pip install cryptography windows-curses")
        print("Done. Please run again.")
        sys.exit(1)
    
    curses.wrapper(main)