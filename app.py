"""
Android Local File Browser - 本地共享文件浏览器
支持主流视频格式解码和图片格式识别 (含 iPhone HEIC/HEIF)
支持文件夹导航浏览
支持多种视频播放器后端切换
"""

import os
import json
import mimetypes
from abc import ABC, abstractmethod
from functools import partial

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.slider import Slider
from kivy.uix.togglebutton import ToggleButton
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform
from kivy.storage.jsonstore import JsonStore
from kivy.metrics import dp

# ──────────────────────────────────────────
# 视频支持检测
# ──────────────────────────────────────────
try:
    from kivy.uix.videoplayer import VideoPlayer as KivyVideoPlayer
    KIVY_VIDEO_SUPPORT = True
except Exception:
    KIVY_VIDEO_SUPPORT = False

try:
    import ffpyplayer  # noqa: F401
    FFPY_SUPPORT = True
except Exception:
    FFPY_SUPPORT = False

# ──────────────────────────────────────────
# 图片支持检测
# ──────────────────────────────────────────
try:
    from PIL import Image as PILImage
    import pillow_heif
    pillow_heif.register_heif_opener()
    PIL_SUPPORT = True
except Exception:
    PIL_SUPPORT = False


# ========== 媒体格式定义 ==========
VIDEO_EXTENSIONS = {
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv',
    '.webm', '.m4v', '.mpg', '.mpeg', '.3gp', '.ts',
    '.ogv', '.ogm',
}

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.tiff', '.tif', '.svg', '.ico',
    '.heic', '.heif', '.heics', '.heifs',
}

ALL_MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS


def get_file_type(filename):
    """获取文件类型: video, image, other, 或 folder"""
    ext = os.path.splitext(filename)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return 'video'
    elif ext in IMAGE_EXTENSIONS:
        return 'image'
    return 'other'


def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 0:
        return ''
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ========== 播放器后端系统 ==========

class PlayerBackend(ABC):
    """播放器后端抽象基类"""

    @abstractmethod
    def get_player_widget(self, source, **kwargs):
        """创建并返回一个可播放视频的 Kivy Widget"""
        pass

    @abstractmethod
    def get_name(self):
        """返回播放器显示名称"""
        pass

    @abstractmethod
    def is_available(self):
        """检测当前环境是否支持此播放器"""
        pass


class KivyVideoBackend(PlayerBackend):
    """Kivy 内置 VideoPlayer 播放器"""

    def get_name(self):
        return "Kivy 内置播放器"

    def is_available(self):
        return KIVY_VIDEO_SUPPORT

    def get_player_widget(self, source, **kwargs):
        player = KivyVideoPlayer(source=source, state='play')
        if 'size_hint' in kwargs:
            player.size_hint = kwargs['size_hint']
        return player


class FfpyplayerBackend(PlayerBackend):
    """基于 ffpyplayer 的视频播放器"""

    def get_name(self):
        return "FFmpeg 播放器 (ffpyplayer)"

    def is_available(self):
        return FFPY_SUPPORT

    def get_player_widget(self, source, **kwargs):
        try:
            from kivy.uix.video import Video
            player = Video(source=source, state='play')
            if 'size_hint' in kwargs:
                player.size_hint = kwargs['size_hint']
            return player
        except Exception:
            raise RuntimeError("ffpyplayer 初始化失败")


class PlayerManager:
    """播放器后端管理器（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._backends = []
            cls._instance._current_index = 0
            cls._instance._register_defaults()
        return cls._instance

    @classmethod
    def _register_defaults(cls):
        instance = cls._instance
        # 按优先级注册可用后端
        instance.register(KivyVideoBackend())
        try:
            instance.register(FfpyplayerBackend())
        except Exception:
            pass

    def register(self, backend):
        """注册一个新的播放器后端"""
        self._backends.append(backend)

    @property
    def available_backends(self):
        """返回所有当前可用的后端"""
        return [b for b in self._backends if b.is_available()]

    @property
    def current_backend(self):
        """获取当前选中的后端"""
        available = self.available_backends
        if not available:
            return None
        idx = min(self._current_index, len(available) - 1)
        return available[idx]

    @current_backend.setter
    def current_backend(self, backend_name):
        """按名称设置当前后端"""
        available = self.available_backends
        for i, b in enumerate(available):
            if b.get_name() == backend_name:
                self._current_index = i
                self._save_setting(backend_name)
                return
        # 如果找不到，默认第一个
        if available:
            self._current_index = 0
            self._save_setting(available[0].get_name())

    def _save_setting(self, name):
        try:
            store = JsonStore(App.get_running_app().settings_path)
            store.put('player_backend', name=name)
        except Exception:
            pass

    def load_setting(self):
        """从持久化存储加载后端设置"""
        try:
            store = JsonStore(App.get_running_app().settings_path)
            saved = store.get('player_backend')['name']
            self.current_backend = saved
        except Exception:
            pass

    def get_player(self, source, **kwargs):
        """获取当前后端创建的播放器组件"""
        backend = self.current_backend
        if backend is None:
            raise RuntimeError("没有可用的视频播放器后端")
        return backend.get_player_widget(source, **kwargs)


# ========== 缩略图 / 文件项组件 ==========

class MediaThumbnail(BoxLayout):
    """文件/文件夹缩略图组件"""
    def __init__(self, filepath, is_dir=False, on_folder_click=None, on_file_click=None, **kwargs):
        super().__init__(**kwargs)
        self.filepath = filepath
        self.is_dir = is_dir
        self.on_folder_click = on_folder_click
        self.on_file_click = on_file_click
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = 180
        self.padding = 4
        self.spacing = 2

        filename = os.path.basename(filepath)

        if is_dir:
            self._build_folder_widget(filename)
        else:
            self._build_file_widget(filename)

    def _build_folder_widget(self, filename):
        """构建文件夹显示"""
        icon_box = BoxLayout(size_hint_y=0.7)
        icon_box.add_widget(Label(text="📁", font_size=48))
        self.add_widget(icon_box)

        name_label = Label(
            text=f"[{filename}]",
            size_hint_y=0.15,
            font_size=11,
            text_size=(160, None),
            halign='center',
            shorten=True,
            shorten_from='right',
            color=(0.6, 0.8, 1.0, 1),
            markup=True,
        )
        self.add_widget(name_label)

        info_label = Label(
            text="文件夹",
            size_hint_y=0.15,
            font_size=10,
            color=(0.6, 0.6, 0.6, 1),
        )
        self.add_widget(info_label)

    def _build_file_widget(self, filename):
        """构建文件显示"""
        filetype = get_file_type(filename)
        filesize = os.path.getsize(self.filepath) if os.path.isfile(self.filepath) else 0

        icon_box = BoxLayout(size_hint_y=0.7)
        if filetype == 'image' and PIL_SUPPORT:
            try:
                img = KivyImage(source=self.filepath, allow_stretch=True, keep_ratio=True)
                icon_box.add_widget(img)
            except Exception:
                icon_box.add_widget(Label(text="🖼️", font_size=40))
        elif filetype == 'video':
            icon_box.add_widget(Label(text="🎬", font_size=40))
        else:
            icon_box.add_widget(Label(text="📄", font_size=40))
        self.add_widget(icon_box)

        name_label = Label(
            text=filename,
            size_hint_y=0.15,
            font_size=11,
            text_size=(160, None),
            halign='center',
            shorten=True,
            shorten_from='right',
        )
        self.add_widget(name_label)

        size_label = Label(
            text=format_size(filesize),
            size_hint_y=0.15,
            font_size=10,
            color=(0.7, 0.7, 0.7, 1),
        )
        self.add_widget(size_label)

    def on_touch_down(self, touch):
        if not self.collide_point(touch.x, touch.y):
            return False
        if self.is_dir and self.on_folder_click:
            self.on_folder_click(self.filepath)
        elif not self.is_dir and self.on_file_click:
            self.on_file_click(self.filepath)
        return True


# ========== 文件浏览器屏幕 ==========

class FileBrowserScreen(Screen):
    """文件浏览器主界面"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_path = self._get_start_path()
        self.current_filter = 'all'
        self._breadcrumb_paths = []
        self._setup_ui()
        # 监听窗口大小变化，动态调整网格列数
        Window.bind(on_resize=self._on_window_resize)

    def _get_start_path(self):
        """获取起始路径"""
        if platform == 'android':
            # 动态请求 Android 存储权限（含 Android 11+ 全存储）
            try:
                from android.permissions import request_permissions, Permission
                perms = [
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                ]
                # Android 11+ 需要 MANAGE_EXTERNAL_STORAGE
                if hasattr(Permission, 'MANAGE_EXTERNAL_STORAGE'):
                    perms.append(Permission.MANAGE_EXTERNAL_STORAGE)
                request_permissions(perms)
            except Exception:
                pass
            # 小米平板 8 内部存储路径
            for path in ['/storage/emulated/0', '/sdcard', '/storage']:
                if os.path.exists(path):
                    return path
            return '/'
        elif os.path.exists('/sdcard'):
            return '/sdcard'
        return os.path.expanduser('~')

    def _setup_ui(self):
        """构建整个 UI"""
        self.layout = BoxLayout(orientation='vertical')
        self.add_widget(self.layout)

        # ── 顶部操作栏 ──
        toolbar = BoxLayout(size_hint_y=0.07, spacing=4, padding=[5, 3])

        btn_back = Button(text='← 返回', size_hint_x=0.15)
        btn_back.bind(on_press=self._go_back)

        btn_up = Button(text='⬆ 上级', size_hint_x=0.15)
        btn_up.bind(on_press=self._go_parent)

        self.path_input = Button(
            text=self.current_path,
            size_hint_x=0.5,
            halign='left',
            valign='middle',
            shorten=True,
            shorten_from='middle',
        )
        self.path_input.bind(on_press=self._edit_path)

        btn_refresh = Button(text='🔄', size_hint_x=0.1)
        btn_refresh.bind(on_press=self._refresh)

        btn_settings = Button(text='⚙', size_hint_x=0.1)
        btn_settings.bind(on_press=self._open_settings)

        toolbar.add_widget(btn_back)
        toolbar.add_widget(btn_up)
        toolbar.add_widget(self.path_input)
        toolbar.add_widget(btn_refresh)
        toolbar.add_widget(btn_settings)
        self.layout.add_widget(toolbar)

        # ── 面包屑导航 ──
        self.breadcrumb_bar = BoxLayout(
            size_hint_y=0.05,
            spacing=2,
            padding=[5, 1],
        )
        self.layout.add_widget(self.breadcrumb_bar)

        # ── 过滤按钮栏 ──
        filter_bar = BoxLayout(size_hint_y=0.06, spacing=3, padding=[5, 2])
        self._filter_buttons = {}
        for key, label in [('all', '全部'), ('folder', '📁 文件夹'),
                           ('video', '🎬 视频'), ('image', '🖼️ 图片'),
                           ('other', '📄 其他')]:
            btn = ToggleButton(
                text=label,
                size_hint_x=0.2,
                group='file_filter',
                state='down' if key == 'all' else 'normal',
            )
            btn.bind(on_press=partial(self._set_filter, key))
            self._filter_buttons[key] = btn
            filter_bar.add_widget(btn)
        self.layout.add_widget(filter_bar)

        # ── 文件列表（可滚动网格，列数动态适配屏幕宽度） ──
        self.scroll_view = ScrollView()
        self._grid_cols = self._calc_grid_cols(Window.width)
        self.grid = GridLayout(cols=self._grid_cols, spacing=dp(5), padding=dp(10), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll_view.add_widget(self.grid)
        self.layout.add_widget(self.scroll_view)

        # ── 底部状态栏 ──
        self.status_label = Label(
            size_hint_y=0.04,
            font_size=12,
            halign='left',
            valign='middle',
            text_size=(Window.width, None),
        )
        self.layout.add_widget(self.status_label)

        self._load_files()

    def _set_filter(self, filter_key, _btn=None):
        """切换过滤条件"""
        self.current_filter = filter_key
        self._load_files()

    def _refresh(self, _instance=None):
        """刷新当前目录"""
        self._load_files()

    def _edit_path(self, _instance=None):
        """弹出路径编辑对话框（后续可扩展为手动输入）"""
        # 简单实现：显示当前路径提示
        self.status_label.text = f"📂 {self.current_path}"

    def _go_back(self, _instance=None):
        """后退到历史访问路径"""
        if self._breadcrumb_paths:
            self.current_path = self._breadcrumb_paths.pop()
            self.path_input.text = self.current_path
            self._load_files()

    def _go_parent(self, _instance=None):
        """进入父目录"""
        parent = os.path.dirname(self.current_path)
        if parent and parent != self.current_path:
            self._breadcrumb_paths.append(self.current_path)
            self.current_path = parent
            self.path_input.text = self.current_path
            self._load_files()

    def _navigate_to(self, folder_path):
        """进入指定文件夹"""
        if os.path.isdir(folder_path):
            self._breadcrumb_paths.append(self.current_path)
            self.current_path = folder_path
            self.path_input.text = self.current_path
            self._load_files()

    def _calc_grid_cols(self, width):
        """根据屏幕宽度计算网格列数（平板使用更多列）"""
        if width > 2000:
            return 6  # 小平板横屏
        elif width > 1500:
            return 5  # 小平板竖屏/大屏手机横屏
        elif width > 1000:
            return 4  # 大屏手机
        else:
            return 3  # 手机

    def _on_window_resize(self, instance, width, height):
        """窗口大小变化时重新调整网格列数"""
        new_cols = self._calc_grid_cols(width)
        if new_cols != self._grid_cols:
            self._grid_cols = new_cols
            self.grid.cols = new_cols
            self._load_files()

    def _open_file(self, file_path):
        """打开文件（图片/视频/其他）"""
        ext = os.path.splitext(file_path)[1].lower()
        ftype = get_file_type(file_path)

        if ftype == 'video':
            self.manager.get_screen('player').play_video(file_path)
            self.manager.current = 'player'
        elif ftype == 'image':
            self._show_image_popup(file_path)
        else:
            self._show_info_popup("提示", f"不支持直接打开此文件类型:\n{file_path}")

    def _show_image_popup(self, file_path):
        """弹出图片查看窗口"""
        content = BoxLayout(orientation='vertical', spacing=5)
        try:
            img = KivyImage(
                source=file_path,
                allow_stretch=True,
                keep_ratio=True,
            )
        except Exception:
            img = Label(text="无法加载图片")
        btn_close = Button(text="关闭", size_hint_y=0.08)
        content.add_widget(img)
        content.add_widget(btn_close)

        popup = Popup(
            title=os.path.basename(file_path),
            content=content,
            size_hint=(0.92, 0.92),
            auto_dismiss=False,
        )
        btn_close.bind(on_press=popup.dismiss)
        popup.open()

    def _show_info_popup(self, title, message):
        """显示信息弹窗"""
        content = BoxLayout(orientation='vertical', spacing=5)
        content.add_widget(Label(text=message))
        btn_close = Button(text="确定", size_hint_y=0.3)
        content.add_widget(btn_close)
        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.7, 0.4),
            auto_dismiss=False,
        )
        btn_close.bind(on_press=popup.dismiss)
        popup.open()

    def _open_settings(self, _instance=None):
        """打开设置面板"""
        self.manager.get_screen('settings').refresh()
        self.manager.current = 'settings'

    def _update_breadcrumb(self):
        """更新面包屑导航"""
        self.breadcrumb_bar.clear_widgets()

        parts = self.current_path.replace('\\', '/').split('/')
        built = ''
        for i, part in enumerate(parts):
            if not part:
                if i == 0:
                    built = '/'
                    btn = Button(
                        text='/',
                        size_hint_x=None,
                        width=30,
                        font_size=11,
                    )
                continue
            built = os.path.join(built, part) if built != '/' else '/' + part
            display = part if len(part) < 15 else part[:12] + '…'
            btn = Button(text=display, size_hint_x=None, width=min(len(part) * 10 + 20, 120), font_size=11)
            btn.bind(on_press=partial(self._navigate_to, built))
            self.breadcrumb_bar.add_widget(btn)

    def _load_files(self):
        """加载当前目录的文件和文件夹列表"""
        self.grid.clear_widgets()
        self._update_breadcrumb()

        # ── 读取目录内容 ──
        try:
            entries = sorted(os.listdir(self.current_path))
        except PermissionError:
            self.status_label.text = '⚠️ 无权限访问此目录'
            return
        except FileNotFoundError:
            self.status_label.text = '⚠️ 路径不存在'
            return

        folders = []
        files = []

        for entry in entries:
            full_path = os.path.join(self.current_path, entry)
            if os.path.isdir(full_path):
                folders.append((full_path, entry))
            elif os.path.isfile(full_path):
                files.append((full_path, entry))

        # ── 列出文件夹 ──
        count = {'video': 0, 'image': 0, 'other': 0, 'folder': 0}

        for fpath, fname in folders:
            if self.current_filter in ('all', 'folder'):
                thumb = MediaThumbnail(
                    fpath, is_dir=True,
                    on_folder_click=self._navigate_to,
                    on_file_click=self._open_file,
                )
                self.grid.add_widget(thumb)
                count['folder'] += 1

        # ── 列出文件 ──
        for fpath, fname in files:
            ftype = get_file_type(fname)
            if self.current_filter != 'all' and ftype != self.current_filter:
                continue

            count[ftype] += 1
            thumb = MediaThumbnail(
                fpath, is_dir=False,
                on_folder_click=self._navigate_to,
                on_file_click=self._open_file,
            )
            self.grid.add_widget(thumb)

        total = sum(count.values())
        info_parts = [f"📂 {self.current_path}"]
        if count['folder']:
            info_parts.append(f"📁 {count['folder']}")
        if count['video']:
            info_parts.append(f"🎬 {count['video']}")
        if count['image']:
            info_parts.append(f"🖼️ {count['image']}")
        info_parts.append(f"总计 {total}")
        self.status_label.text = '  |  '.join(info_parts)


# ========== 全屏播放器屏幕 ==========

class PlayerScreen(Screen):
    """专门的视频/媒体播放屏幕"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_source = None
        self._player_widget = None
        self._setup_ui()

    def _setup_ui(self):
        self.layout = BoxLayout(orientation='vertical')

        # 视频画面区（占满）
        self.video_container = BoxLayout()
        self.layout.add_widget(self.video_container)

        # 控制栏
        controls = BoxLayout(size_hint_y=0.08, spacing=5, padding=5)

        btn_back = Button(text='← 返回浏览器', size_hint_x=0.4)
        btn_back.bind(on_press=self._return_to_browser)

        btn_pause = Button(text='⏸ 暂停/继续', size_hint_x=0.3)
        btn_pause.bind(on_press=self._toggle_pause)

        btn_stop = Button(text='⏹ 停止', size_hint_x=0.3)
        btn_stop.bind(on_press=self._stop_playback)

        controls.add_widget(btn_back)
        controls.add_widget(btn_pause)
        controls.add_widget(btn_stop)
        self.layout.add_widget(controls)

        # 状态/文件名提示
        self.info_label = Label(
            size_hint_y=0.04,
            font_size=12,
            halign='center',
        )
        self.layout.add_widget(self.info_label)

        self.add_widget(self.layout)

    def play_video(self, source):
        """播放视频文件"""
        self._current_source = source
        self.info_label.text = os.path.basename(source)

        # 清空旧播放器
        self.video_container.clear_widgets()
        if self._player_widget:
            try:
                self._player_widget.state = 'stop'
            except Exception:
                pass
            self._player_widget = None

        # 创建新播放器
        try:
            pm = PlayerManager()
            self._player_widget = pm.get_player(source, size_hint=(1, 1))
            self.video_container.add_widget(self._player_widget)
        except Exception as e:
            err_label = Label(text=f"无法播放视频:\n{str(e)}")
            self.video_container.add_widget(err_label)

    def _toggle_pause(self, _instance=None):
        """切换暂停/播放"""
        if self._player_widget and hasattr(self._player_widget, 'state'):
            if self._player_widget.state == 'play':
                self._player_widget.state = 'pause'
            else:
                self._player_widget.state = 'play'

    def _stop_playback(self, _instance=None):
        """停止播放"""
        if self._player_widget and hasattr(self._player_widget, 'state'):
            self._player_widget.state = 'stop'

    def _return_to_browser(self, _instance=None):
        """返回文件浏览器"""
        if self._player_widget and hasattr(self._player_widget, 'state'):
            self._player_widget.state = 'stop'
        self.manager.current = 'browser'


# ========== 设置屏幕 ==========

class SettingsScreen(Screen):
    """设置面板——播放器后端切换等"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_ui()

    def _setup_ui(self):
        self.layout = BoxLayout(orientation='vertical', spacing=10, padding=15)
        self.add_widget(self.layout)

        # 标题
        title = Label(
            text="⚙ 设置",
            font_size=22,
            size_hint_y=0.1,
            bold=True,
        )
        self.layout.add_widget(title)

        # ── 播放器后端选择 ──
        section_label = Label(
            text="视频播放器后端",
            font_size=16,
            size_hint_y=0.07,
            halign='left',
            color=(0.7, 0.9, 1, 1),
        )
        self.layout.add_widget(section_label)

        self.player_btn_group = []
        self.player_btn_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=5,
        )

        pm = PlayerManager()
        available = pm.available_backends

        if not available:
            self.player_btn_layout.add_widget(Label(text="没有可用的播放器后端"))
        else:
            for backend in available:
                btn = ToggleButton(
                    text=f"  {backend.get_name()}",
                    size_hint_y=None,
                    height=50,
                    group='player_backend',
                    state='down' if backend == pm.current_backend else 'normal',
                )
                btn.backend_name = backend.get_name()
                btn.bind(on_press=self._select_player_backend)
                self.player_btn_group.append(btn)
                self.player_btn_layout.add_widget(btn)

            # 动态高度
            self.player_btn_layout.height = len(available) * 55
        self.layout.add_widget(self.player_btn_layout)

        # ── 关于信息 ──
        self.layout.add_widget(BoxLayout(size_hint_y=0.05))

        about_label = Label(
            text=(
                "本地文件浏览器 v2.0\n"
                "基于 Kivy 构建\n"
                "支持 iPhone HEIC/HEIF 图片"
            ),
            font_size=12,
            size_hint_y=0.15,
            color=(0.5, 0.5, 0.5, 1),
        )
        self.layout.add_widget(about_label)

        # ── 返回按钮 ──
        btn_back = Button(text="← 返回浏览器", size_hint_y=0.08)
        btn_back.bind(on_press=self._return_to_browser)
        self.layout.add_widget(btn_back)

        # 弹性填充
        self.layout.add_widget(BoxLayout())

    def _select_player_backend(self, instance):
        """选择播放器后端"""
        if instance.state == 'down':
            pm = PlayerManager()
            pm.current_backend = instance.backend_name

    def refresh(self):
        """刷新设置面板状态"""
        pm = PlayerManager()
        available = pm.available_backends
        for btn in self.player_btn_group:
            if hasattr(btn, 'backend_name'):
                btn.state = 'down' if btn.backend_name == pm.current_backend.get_name() else 'normal'

    def _return_to_browser(self, _instance=None):
        """返回文件浏览器"""
        self.manager.current = 'browser'


# ========== 主应用 ==========

class AndroidFileBrowserApp(App):
    """主应用程序"""
    def build(self):
        self.title = '本地文件浏览器'
        self.settings_path = self._get_settings_path()

        # 加载保存的播放器设置
        pm = PlayerManager()
        pm.load_setting()

        # ScreenManager
        sm = ScreenManager()
        sm.add_widget(FileBrowserScreen(name='browser'))
        sm.add_widget(PlayerScreen(name='player'))
        sm.add_widget(SettingsScreen(name='settings'))
        return sm

    def _get_settings_path(self):
        """获取持久化存储路径"""
        if platform == 'android':
            return os.path.join(os.environ.get('ANDROID_PRIVATE', '.'), 'settings.json')
        user_dir = os.path.expanduser('~')
        app_dir = os.path.join(user_dir, '.android-file-browser')
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, 'settings.json')


if __name__ == '__main__':
    AndroidFileBrowserApp().run()
