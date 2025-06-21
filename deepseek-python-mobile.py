"""
DeepSeek R1 Mobile AI Assistant
A complete Python mobile application using Kivy and Ollama integration
"""

import asyncio
import json
import requests
import threading
from datetime import datetime
from typing import List, Dict, Optional
import os

# Kivy imports for mobile UI
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.switch import Switch
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.actionbar import ActionBar, ActionView, ActionPrevious, ActionButton

class DeepSeekAPI:
    """
    API handler for Ollama DeepSeek R1 integration
    """
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model_name = "deepseek-r1"
        self.session = requests.Session()
        self.is_connected = False
        
    def check_connection(self) -> bool:
        """Check if Ollama server is running and model is available"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model['name'] for model in models]
                self.is_connected = self.model_name in model_names
                return self.is_connected
        except Exception as e:
            print(f"Connection error: {e}")
            self.is_connected = False
            return False
    
    def generate_response(self, prompt: str, context: List[Dict] = None) -> Optional[str]:
        """Generate response from DeepSeek R1"""
        try:
            # Build conversation context
            full_prompt = prompt
            if context:
                conversation = "\n".join([
                    f"Human: {msg['content']}" if msg['role'] == 'user' 
                    else f"Assistant: {msg['content']}" 
                    for msg in context[-10:]  # Last 10 messages for context
                ])
                full_prompt = f"{conversation}\nHuman: {prompt}\nAssistant:"
            
            payload = {
                "model": self.model_name,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 2000
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                return f"Error: HTTP {response.status_code}"
                
        except Exception as e:
            return f"Error generating response: {str(e)}"

class MessageBubble(BoxLayout):
    """Custom message bubble widget"""
    
    def __init__(self, message: str, is_user: bool = False, timestamp: str = "", **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = [10, 5]
        self.spacing = 2
        
        # Main container for the bubble
        bubble_container = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=self.texture_size[1] + 20
        )
        
        if is_user:
            # User message (right side, blue)
            spacer = Widget(size_hint_x=0.2)
            bubble_container.add_widget(spacer)
            
            message_box = BoxLayout(
                orientation='vertical',
                size_hint_x=0.8,
                padding=[15, 10]
            )
            
            with message_box.canvas.before:
                Color(0.2, 0.6, 1, 1)  # Blue color
                self.rect = RoundedRectangle(
                    pos=message_box.pos,
                    size=message_box.size,
                    radius=[15]
                )
                
        else:
            # Assistant message (left side, gray)
            message_box = BoxLayout(
                orientation='vertical',
                size_hint_x=0.8,
                padding=[15, 10]
            )
            
            with message_box.canvas.before:
                Color(0.3, 0.3, 0.3, 1)  # Gray color
                self.rect = RoundedRectangle(
                    pos=message_box.pos,
                    size=message_box.size,
                    radius=[15]
                )
            
            spacer = Widget(size_hint_x=0.2)
            bubble_container.add_widget(spacer)
        
        # Message text
        message_label = Label(
            text=message,
            text_size=(None, None),
            halign='left',
            valign='top',
            color=[1, 1, 1, 1],
            font_size='14sp'
        )
        message_label.bind(texture_size=message_label.setter('size'))
        message_box.add_widget(message_label)
        
        # Timestamp
        if timestamp:
            time_label = Label(
                text=timestamp,
                font_size='10sp',
                color=[0.7, 0.7, 0.7, 1],
                size_hint_y=None,
                height='15dp'
            )
            message_box.add_widget(time_label)
        
        bubble_container.add_widget(message_box)
        self.add_widget(bubble_container)
        
        # Bind to update rectangle position
        message_box.bind(pos=self.update_rect, size=self.update_rect)
    
    def update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

class ChatScreen(Screen):
    """Main chat interface screen"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api = DeepSeekAPI()
        self.conversation_history = []
        self.build_ui()
        
        # Check connection on startup
        Clock.schedule_once(self.check_connection, 1)
    
    def build_ui(self):
        """Build the chat interface"""
        main_layout = BoxLayout(orientation='vertical')
        
        # Action bar / Header
        action_bar = ActionBar()
        action_view = ActionView()
        action_previous = ActionPrevious(
            title='DeepSeek R1 Assistant',
            with_previous=False
        )
        
        # Connection status button
        self.connection_btn = ActionButton(
            text='●',
            color=[1, 0, 0, 1]  # Red initially
        )
        
        # Settings button
        settings_btn = ActionButton(text='⚙')
        settings_btn.bind(on_press=self.show_settings)
        
        # Clear chat button
        clear_btn = ActionButton(text='🗑')
        clear_btn.bind(on_press=self.clear_chat)
        
        action_view.add_widget(action_previous)
        action_view.add_widget(self.connection_btn)
        action_view.add_widget(settings_btn)
        action_view.add_widget(clear_btn)
        action_bar.add_widget(action_view)
        
        # Chat messages area
        self.scroll_view = ScrollView()
        self.messages_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=5,
            padding=[10, 10]
        )
        self.messages_layout.bind(minimum_height=self.messages_layout.setter('height'))
        self.scroll_view.add_widget(self.messages_layout)
        
        # Input area
        input_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height='50dp',
            padding=[10, 5],
            spacing=10
        )
        
        self.text_input = TextInput(
            hint_text='Type your message...',
            multiline=False,
            size_hint_x=0.8
        )
        self.text_input.bind(on_text_validate=self.send_message)
        
        self.send_btn = Button(
            text='Send',
            size_hint_x=0.2,
            background_color=[0.2, 0.6, 1, 1]
        )
        self.send_btn.bind(on_press=self.send_message)
        
        input_layout.add_widget(self.text_input)
        input_layout.add_widget(self.send_btn)
        
        # Add welcome message
        self.add_message("Hello! I'm DeepSeek R1. How can I help you today?", False)
        
        # Assemble main layout
        main_layout.add_widget(action_bar)
        main_layout.add_widget(self.scroll_view)
        main_layout.add_widget(input_layout)
        
        self.add_widget(main_layout)
    
    def add_message(self, text: str, is_user: bool = False):
        """Add a message to the chat"""
        timestamp = datetime.now().strftime("%H:%M")
        message_bubble = MessageBubble(text, is_user, timestamp)
        self.messages_layout.add_widget(message_bubble)
        
        # Scroll to bottom
        Clock.schedule_once(lambda dt: setattr(self.scroll_view, 'scroll_y', 0), 0.1)
        
        # Store in conversation history
        self.conversation_history.append({
            'role': 'user' if is_user else 'assistant',
            'content': text,
            'timestamp': timestamp
        })
    
    def send_message(self, instance=None):
        """Send user message and get AI response"""
        message = self.text_input.text.strip()
        if not message:
            return
        
        # Add user message
        self.add_message(message, True)
        self.text_input.text = ''
        
        # Show typing indicator
        typing_bubble = MessageBubble("● ● ● Thinking...", False)
        self.messages_layout.add_widget(typing_bubble)
        
        # Get AI response in background thread
        threading.Thread(
            target=self.get_ai_response,
            args=(message, typing_bubble),
            daemon=True
        ).start()
    
    def get_ai_response(self, user_message: str, typing_bubble):
        """Get response from AI in background thread"""
        response = self.api.generate_response(user_message, self.conversation_history)
        
        # Update UI on main thread
        Clock.schedule_once(
            lambda dt: self.update_with_response(response, typing_bubble), 0
        )
    
    @mainthread
    def update_with_response(self, response: str, typing_bubble):
        """Update UI with AI response"""
        # Remove typing indicator
        self.messages_layout.remove_widget(typing_bubble)
        
        # Add AI response
        self.add_message(response, False)
    
    def check_connection(self, dt=None):
        """Check API connection status"""
        def check():
            is_connected = self.api.check_connection()
            Clock.schedule_once(
                lambda dt: self.update_connection_status(is_connected), 0
            )
        
        threading.Thread(target=check, daemon=True).start()
    
    @mainthread
    def update_connection_status(self, is_connected: bool):
        """Update connection status indicator"""
        if is_connected:
            self.connection_btn.color = [0, 1, 0, 1]  # Green
        else:
            self.connection_btn.color = [1, 0, 0, 1]  # Red
    
    def show_settings(self, instance):
        """Show settings popup"""
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # Ollama URL setting
        url_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        url_layout.add_widget(Label(text='Ollama URL:', size_hint_x=0.3))
        url_input = TextInput(text=self.api.base_url, size_hint_x=0.7)
        url_layout.add_widget(url_input)
        content.add_widget(url_layout)
        
        # Model name setting
        model_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        model_layout.add_widget(Label(text='Model:', size_hint_x=0.3))
        model_input = TextInput(text=self.api.model_name, size_hint_x=0.7)
        model_layout.add_widget(model_input)
        content.add_widget(model_layout)
        
        # Instructions
        instructions = Label(
            text='Make sure to run:\nollama run deepseek-r1',
            text_size=(None, None),
            halign='center'
        )
        content.add_widget(instructions)
        
        # Buttons
        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        
        def save_settings(instance):
            self.api.base_url = url_input.text
            self.api.model_name = model_input.text
            self.check_connection()
            popup.dismiss()
        
        def test_connection(instance):
            self.check_connection()
        
        save_btn = Button(text='Save')
        save_btn.bind(on_press=save_settings)
        
        test_btn = Button(text='Test Connection')
        test_btn.bind(on_press=test_connection)
        
        cancel_btn = Button(text='Cancel')
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        
        btn_layout.add_widget(save_btn)
        btn_layout.add_widget(test_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(btn_layout)
        
        popup = Popup(
            title='Settings',
            content=content,
            size_hint=(0.8, 0.6)
        )
        popup.open()
    
    def clear_chat(self, instance):
        """Clear all messages"""
        self.messages_layout.clear_widgets()
        self.conversation_history.clear()
        self.add_message("Hello! I'm DeepSeek R1. How can I help you today?", False)

class DeepSeekMobileApp(App):
    """Main application class"""
    
    def build(self):
        # Set window properties for mobile
        Window.clearcolor = get_color_from_hex('#1a1a1a')
        
        # Create screen manager
        sm = ScreenManager()
        
        # Add chat screen
        chat_screen = ChatScreen(name='chat')
        sm.add_widget(chat_screen)
        
        return sm
    
    def on_start(self):
        """Called when app starts"""
        print("DeepSeek R1 Mobile Assistant Started")
        print("Make sure Ollama is running with: ollama run deepseek-r1")
    
    def on_stop(self):
        """Called when app stops"""
        print("DeepSeek R1 Mobile Assistant Stopped")

# Entry point
if __name__ == '__main__':
    DeepSeekMobileApp().run()
