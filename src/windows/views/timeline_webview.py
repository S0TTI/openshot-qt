""" 
 @file
 @brief This file loads the interactive HTML timeline
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <eolinwen@gmail.com>
 
 @section LICENSE
 
 Copyright (c) 2008-2016 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.
 
 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 
 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.
 
 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import os
from copy import deepcopy
from functools import partial
from random import uniform
from urllib.parse import urlparse

import openshot  # Python module for libopenshot (required video editing module installed separately)
from PyQt5.QtCore import QFileInfo, pyqtSlot, QUrl, Qt, QCoreApplication, QTimer
from PyQt5.QtGui import QCursor, QKeySequence
from PyQt5.QtWebKitWidgets import QWebView
from PyQt5.QtWidgets import QMenu

from classes import info, updates
from classes import settings
from classes.app import get_app
from classes.logger import log
from classes.query import File, Clip, Transition, Track
from classes.waveform import get_audio_data

try:
    import json
except ImportError:
    import simplejson as json

# Constants used by this file
JS_SCOPE_SELECTOR = "$('body').scope()"

MENU_FADE_NONE = 0
MENU_FADE_IN_FAST = 1
MENU_FADE_IN_SLOW = 2
MENU_FADE_OUT_FAST = 3
MENU_FADE_OUT_SLOW = 4
MENU_FADE_IN_OUT_FAST = 5
MENU_FADE_IN_OUT_SLOW = 6

MENU_ROTATE_NONE = 0
MENU_ROTATE_90_RIGHT = 1
MENU_ROTATE_90_LEFT = 2
MENU_ROTATE_180_FLIP = 3

MENU_LAYOUT_NONE = 0
MENU_LAYOUT_CENTER = 1
MENU_LAYOUT_TOP_LEFT = 2
MENU_LAYOUT_TOP_RIGHT = 3
MENU_LAYOUT_BOTTOM_LEFT = 4
MENU_LAYOUT_BOTTOM_RIGHT = 5
MENU_LAYOUT_ALL_WITH_ASPECT = 6
MENU_LAYOUT_ALL_WITHOUT_ASPECT = 7

MENU_ALIGN_LEFT = 0
MENU_ALIGN_RIGHT = 1

MENU_ANIMATE_NONE = 0
MENU_ANIMATE_IN_50_100 = 1
MENU_ANIMATE_IN_75_100 = 2
MENU_ANIMATE_IN_100_150 = 3
MENU_ANIMATE_OUT_100_75 = 4
MENU_ANIMATE_OUT_100_50 = 5
MENU_ANIMATE_OUT_150_100 = 6
MENU_ANIMATE_CENTER_TOP = 7
MENU_ANIMATE_CENTER_LEFT = 8
MENU_ANIMATE_CENTER_RIGHT = 9
MENU_ANIMATE_CENTER_BOTTOM = 10
MENU_ANIMATE_TOP_CENTER = 11
MENU_ANIMATE_LEFT_CENTER = 12
MENU_ANIMATE_RIGHT_CENTER = 13
MENU_ANIMATE_BOTTOM_CENTER = 14
MENU_ANIMATE_TOP_BOTTOM = 15
MENU_ANIMATE_LEFT_RIGHT = 16
MENU_ANIMATE_RIGHT_LEFT = 17
MENU_ANIMATE_BOTTOM_TOP = 18
MENU_ANIMATE_RANDOM = 19

MENU_VOLUME_NONE = 1
MENU_VOLUME_FADE_IN_FAST = 2
MENU_VOLUME_FADE_IN_SLOW = 3
MENU_VOLUME_FADE_OUT_FAST = 4
MENU_VOLUME_FADE_OUT_SLOW = 5
MENU_VOLUME_FADE_IN_OUT_FAST = 6
MENU_VOLUME_FADE_IN_OUT_SLOW = 7
MENU_VOLUME_LEVEL_100 = 100
MENU_VOLUME_LEVEL_90 = 90
MENU_VOLUME_LEVEL_80 = 80
MENU_VOLUME_LEVEL_70 = 70
MENU_VOLUME_LEVEL_60 = 60
MENU_VOLUME_LEVEL_50 = 50
MENU_VOLUME_LEVEL_40 = 40
MENU_VOLUME_LEVEL_30 = 30
MENU_VOLUME_LEVEL_20 = 20
MENU_VOLUME_LEVEL_10 = 10
MENU_VOLUME_LEVEL_0 = 0

MENU_TRANSFORM = 0

MENU_TIME_NONE = 0
MENU_TIME_FORWARD = 1
MENU_TIME_BACKWARD = 2

MENU_COPY_ALL = -1
MENU_COPY_CLIP = 0
MENU_COPY_KEYFRAMES_ALL = 1
MENU_COPY_KEYFRAMES_ALPHA = 2
MENU_COPY_KEYFRAMES_SCALE = 3
MENU_COPY_KEYFRAMES_ROTATE = 4
MENU_COPY_KEYFRAMES_LOCATION = 5
MENU_COPY_KEYFRAMES_TIME = 6
MENU_COPY_KEYFRAMES_VOLUME = 7
MENU_COPY_EFFECTS = 8
MENU_PASTE = 9

MENU_COPY_TRANSITION = 10
MENU_COPY_KEYFRAMES_BRIGHTNESS = 11
MENU_COPY_KEYFRAMES_CONTRAST = 12

MENU_SLICE_KEEP_BOTH = 0
MENU_SLICE_KEEP_LEFT = 1
MENU_SLICE_KEEP_RIGHT = 2

MENU_SPLIT_AUDIO_SINGLE = 0
MENU_SPLIT_AUDIO_MULTIPLE = 1


class TimelineWebView(QWebView, updates.UpdateInterface):
    """ A WebView QWidget used to load the Timeline """

    # Path to html file
    html_path = os.path.join(info.PATH, 'timeline', 'index.html')

    def eval_js(self, code):
        return self.page().mainFrame().evaluateJavaScript(code)

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):
        # Send a JSON version of the UpdateAction to the timeline webview method: ApplyJsonDiff()
        if action.type == "load":
            # Initialize translated track name
            _ = get_app()._tr
            self.eval_js(JS_SCOPE_SELECTOR + ".SetTrackLabel('" + _("Track %s") + "');")

            # Load entire project data
            code = JS_SCOPE_SELECTOR + ".LoadJson(" + action.json() + ");"
        else:
            # Apply diff to part of project data
            code = JS_SCOPE_SELECTOR + ".ApplyJsonDiff([" + action.json() + "]);"
        self.eval_js(code)

        # Reset the scale when loading new JSON
        if action.type == "load":
            # Set the scale again (to project setting)
            initial_scale = get_app().project.get(["scale"]) or 20
            get_app().window.sliderZoom.setValue(initial_scale)

    # Javascript callable function to update the project data when a clip changes
    @pyqtSlot(str)
    def update_clip_data(self, clip_json, only_basic_props=True, ignore_reader=False):
        """ Create an updateAction and send it to the update manager """

        # read clip json
        try:
            if not isinstance(clip_json, dict):
                clip_data = json.loads(clip_json)
            else:
                clip_data = clip_json
        except:
            # Failed to parse json, do nothing
            return

        # Search for matching clip in project data (if any)
        existing_clip = Clip.get(id=clip_data["id"])
        if not existing_clip:
            # Create a new clip (if not exists)
            existing_clip = Clip()

        # Determine if "start" changed
        start_changed = False
        if existing_clip.data and existing_clip.data["start"] != clip_data["start"] and clip_data["reader"]["has_video"] and not clip_data["reader"]["has_single_image"]:
            # Update thumbnail
            self.UpdateClipThumbnail(clip_data)

        # Update clip data
        existing_clip.data = clip_data

        # Remove unneeded properties (since they don't change here... this is a performance boost)
        if only_basic_props:
            existing_clip.data = {}
            existing_clip.data["id"] = clip_data["id"]
            existing_clip.data["layer"] = clip_data["layer"]
            existing_clip.data["position"] = clip_data["position"]
            existing_clip.data["image"] = clip_data["image"]
            existing_clip.data["start"] = clip_data["start"]
            existing_clip.data["end"] = clip_data["end"]

        # Always remove the Reader attribute (since nothing updates it, and we are wrapping clips in FrameMappers anyway)
        if ignore_reader and "reader" in existing_clip.data:
            existing_clip.data.pop("reader")

        # Save clip
        existing_clip.save()

        # Update the preview and reselct current frame in properties
        get_app().window.refreshFrameSignal.emit()
        get_app().window.propertyTableView.select_frame(self.window.preview_thread.player.Position())

    # Update Thumbnails for modified clips
    def UpdateClipThumbnail(self, clip_data):
        """Update the thumbnail image for clips"""

        # Get project's frames per second
        fps = clip_data["reader"]["fps"]
        fps_float = float(fps["num"]) / float(fps["den"])

        # Get starting time of clip
        start_frame = round(float(clip_data["start"]) * fps_float) + 1

        # Determine thumb path
        thumb_path = os.path.join(info.THUMBNAIL_PATH, "{}-{}.png".format(clip_data["id"], start_frame))
        log.info('Updating thumbnail image: %s' % thumb_path)

        # Check if thumb exists
        if not os.path.exists(thumb_path):

            # Get file object
            file = File.get(id=clip_data["file_id"])

            # Convert path to the correct relative path (based on this folder)
            file_path = file.absolute_path()

            # Reload this reader
            clip = openshot.Clip(file_path)
            reader = clip.Reader()

            # Open reader
            reader.Open()

            # Determine if video overlay should be applied to thumbnail
            overlay_path = ""
            if file.data["media_type"] == "video":
                overlay_path = os.path.join(info.IMAGES_PATH, "overlay.png")

            # Save thumbnail
            reader.GetFrame(start_frame).Thumbnail(thumb_path, 98, 64, os.path.join(info.IMAGES_PATH, "mask.png"),
                                         overlay_path, "#000", False)
            reader.Close()
            clip.Close()

            # Update clip_data to point to new thumbnail image
            clip_data["image"] = thumb_path

    # Add missing transition
    @pyqtSlot(str)
    def add_missing_transition(self, transition_json):

        transition_details = json.loads(transition_json)

        # Get FPS from project
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Open up QtImageReader for transition Image
        transition_reader = openshot.QtImageReader(
            os.path.join(info.PATH, "transitions", "common", "fade.svg"))

        # Generate transition object
        transition_object = openshot.Mask()

        # Set brightness and contrast, to correctly transition for overlapping clips
        brightness = transition_object.brightness
        brightness.AddPoint(1, 1.0, openshot.BEZIER)
        brightness.AddPoint(round(transition_details["end"] * fps_float) + 1, -1.0, openshot.BEZIER)
        contrast = openshot.Keyframe(3.0)

        # Create transition dictionary
        transitions_data = {
            "id": get_app().project.generate_id(),
            "layer": transition_details["layer"],
            "title": "Transition",
            "type": "Mask",
            "position": transition_details["position"],
            "start": transition_details["start"],
            "end": transition_details["end"],
            "brightness": json.loads(brightness.Json()),
            "contrast": json.loads(contrast.Json()),
            "reader": json.loads(transition_reader.Json()),
            "replace_image": False
        }

        # Send to update manager
        self.update_transition_data(transitions_data, only_basic_props=False)

    # Javascript callable function to update the project data when a transition changes
    @pyqtSlot(str)
    def update_transition_data(self, transition_json, only_basic_props=True):
        """ Create an updateAction and send it to the update manager """

        # read clip json
        if not isinstance(transition_json, dict):
            transition_data = json.loads(transition_json)
        else:
            transition_data = transition_json

        # Search for matching clip in project data (if any)
        existing_item = Transition.get(id=transition_data["id"])
        needs_resize = True
        if not existing_item:
            # Create a new clip (if not exists)
            existing_item = Transition()
            needs_resize = False
        existing_item.data = transition_data

        # Get FPS from project
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])
        duration = existing_item.data["end"] - existing_item.data["start"]

        # Update the brightness and contrast keyframes to match the duration of the transition
        # This is a hack until I can think of something better
        brightness = None
        contrast = None
        if needs_resize:
            # Adjust transition's brightness keyframes to match the size of the transition
            brightness = existing_item.data["brightness"]
            if len(brightness["Points"]) > 1:
                # If multiple points, move the final one to the 'new' end
                brightness["Points"][-1]["co"]["X"] = round(duration * fps_float) + 1

            # Adjust transition's contrast keyframes to match the size of the transition
            contrast = existing_item.data["contrast"]
            if len(contrast["Points"]) > 1:
                # If multiple points, move the final one to the 'new' end
                contrast["Points"][-1]["co"]["X"] = round(duration * fps_float) + 1
        else:
            # Create new brightness and contrast Keyframes
            b = openshot.Keyframe()
            b.AddPoint(1, 1.0, openshot.BEZIER)
            b.AddPoint(round(duration * fps_float) + 1, -1.0, openshot.BEZIER)
            brightness = json.loads(b.Json())

        # Only include the basic properties (performance boost)
        if only_basic_props:
            existing_item.data = {}
            existing_item.data["id"] = transition_data["id"]
            existing_item.data["layer"] = transition_data["layer"]
            existing_item.data["position"] = transition_data["position"]
            existing_item.data["start"] = transition_data["start"]
            existing_item.data["end"] = transition_data["end"]

            log.info('transition start: %s' % transition_data["start"])
            log.info('transition end: %s' % transition_data["end"])

            if brightness:
                existing_item.data["brightness"] = brightness
            if contrast:
                existing_item.data["contrast"] = contrast

        # Save transition
        existing_item.save()

        # Update the preview and reselct current frame in properties
        get_app().window.refreshFrameSignal.emit()
        get_app().window.propertyTableView.select_frame(self.window.preview_thread.player.Position())

    # Prevent default context menu, and ignore, so that javascript can intercept
    def contextMenuEvent(self, event):
        event.ignore()

    # Javascript callable function to show clip or transition content menus, passing in type to show
    @pyqtSlot(float)
    def ShowPlayheadMenu(self, position=None):
        log.info('ShowPlayheadMenu: %s' % position)

        # Get translation method
        _ = get_app()._tr

        # Get list of intercepting clips with position (if any)
        intersecting_clips = Clip.filter(intersect=position)
        intersecting_trans = Transition.filter(intersect=position)

        menu = QMenu(self)
        if intersecting_clips or intersecting_trans:
            # Get list of clip ids
            clip_ids = [c.id for c in intersecting_clips]
            trans_ids = [t.id for t in intersecting_trans]

            # Add split clip menu
            Slice_Menu = QMenu(_("Slice All"), self)
            Slice_Keep_Both = Slice_Menu.addAction(_("Keep Both Sides"))
            Slice_Keep_Both.triggered.connect(partial(self.Slice_Triggered, MENU_SLICE_KEEP_BOTH, clip_ids, trans_ids, position))
            Slice_Keep_Left = Slice_Menu.addAction(_("Keep Left Side"))
            Slice_Keep_Left.triggered.connect(partial(self.Slice_Triggered, MENU_SLICE_KEEP_LEFT, clip_ids, trans_ids, position))
            Slice_Keep_Right = Slice_Menu.addAction(_("Keep Right Side"))
            Slice_Keep_Right.triggered.connect(partial(self.Slice_Triggered, MENU_SLICE_KEEP_RIGHT, clip_ids, trans_ids, position))
            menu.addMenu(Slice_Menu)
            return menu.popup(QCursor.pos())

    @pyqtSlot(str)
    def ShowEffectMenu(self, effect_id=None):
        log.info('ShowEffectMenu: %s' % effect_id)

        # Set the selected clip (if needed)
        self.window.addSelection(effect_id, 'effect', True)

        menu = QMenu(self)
        # Properties
        menu.addAction(self.window.actionProperties)

        # Remove Effect Menu
        menu.addSeparator()
        menu.addAction(self.window.actionRemoveEffect)
        return menu.popup(QCursor.pos())

    @pyqtSlot(float, int)
    def ShowTimelineMenu(self, position, layer_id):
        log.info('ShowTimelineMenu: position: %s, layer: %s' % (position, layer_id))

        # Get translation method
        _ = get_app()._tr

        # Get list of clipboard items (that are complete clips or transitions)
        # i.e. ignore partial clipboard items (keyframes / effects / etc...)
        clipboard_clip_ids = [k for k, v in self.copy_clipboard.items() if v.get('id')]
        clipboard_tran_ids = [k for k, v in self.copy_transition_clipboard.items() if v.get('id')]

        # Paste Menu (if entire cilps or transitions are copied)
        if self.copy_clipboard or self.copy_transition_clipboard:
            if len(clipboard_clip_ids) + len(clipboard_tran_ids) > 0:
                menu = QMenu(self)
                Paste_Clip = menu.addAction(_("Paste"))
                Paste_Clip.setShortcut(QKeySequence(self.window.getShortcutByName("pasteAll")))
                Paste_Clip.triggered.connect(partial(self.Paste_Triggered, MENU_PASTE, float(position), int(layer_id), [], []))

                return menu.popup(QCursor.pos())

    @pyqtSlot(str)
    def ShowClipMenu(self, clip_id=None):
        log.info('ShowClipMenu: %s' % clip_id)

        # Get translation method
        _ = get_app()._tr

        # Set the selected clip (if needed)
        if clip_id not in self.window.selected_clips:
            self.window.addSelection(clip_id, 'clip')
        # Get list of selected clips
        clip_ids = self.window.selected_clips
        tran_ids = self.window.selected_transitions

        # Get framerate
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Get existing clip object
        clip = Clip.get(id=clip_id)
        playhead_position = float(self.window.preview_thread.current_frame) / fps_float

        # Mark these strings for translation
        translations = [_("Start of Clip"), _("End of Clip"), _("Entire Clip"), _("Normal"), _("Fast"), _("Slow"), _("Forward"), _("Backward")]

        # Create blank context menu
        menu = QMenu(self)

        # Copy Menu
        if len(tran_ids) + len(clip_ids) > 1:
            # Show Copy All menu (clips and transitions are selected)
            Copy_All = menu.addAction(_("Copy"))
            Copy_All.setShortcut(QKeySequence(self.window.getShortcutByName("copyAll")))
            Copy_All.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_ALL, clip_ids, tran_ids))
        else:
            # Only a single clip is selected (Show normal copy menus)
            Copy_Menu = QMenu(_("Copy"), self)
            Copy_Clip = Copy_Menu.addAction(_("Clip"))
            Copy_Clip.setShortcut(QKeySequence(self.window.getShortcutByName("copyAll")))
            Copy_Clip.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_CLIP, [clip_id], []))

            Keyframe_Menu = QMenu(_("Keyframes"), self)
            Copy_Keyframes_All = Keyframe_Menu.addAction(_("All"))
            Copy_Keyframes_All.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_KEYFRAMES_ALL, [clip_id], []))
            Keyframe_Menu.addSeparator()
            Copy_Keyframes_Alpha = Keyframe_Menu.addAction(_("Alpha"))
            Copy_Keyframes_Alpha.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_KEYFRAMES_ALPHA, [clip_id], []))
            Copy_Keyframes_Scale = Keyframe_Menu.addAction(_("Scale"))
            Copy_Keyframes_Scale.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_KEYFRAMES_SCALE, [clip_id], []))
            Copy_Keyframes_Rotate = Keyframe_Menu.addAction(_("Rotation"))
            Copy_Keyframes_Rotate.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_KEYFRAMES_ROTATE, [clip_id], []))
            Copy_Keyframes_Locate = Keyframe_Menu.addAction(_("Location"))
            Copy_Keyframes_Locate.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_KEYFRAMES_LOCATION, [clip_id], []))
            Copy_Keyframes_Time = Keyframe_Menu.addAction(_("Time"))
            Copy_Keyframes_Time.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_KEYFRAMES_TIME, [clip_id], []))
            Copy_Keyframes_Volume = Keyframe_Menu.addAction(_("Volume"))
            Copy_Keyframes_Volume.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_KEYFRAMES_VOLUME, [clip_id], []))

            # Only add copy->effects and copy->keyframes if 1 clip is selected
            Copy_Effects = Copy_Menu.addAction(_("Effects"))
            Copy_Effects.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_EFFECTS, [clip_id], []))
            Copy_Menu.addMenu(Keyframe_Menu)
            menu.addMenu(Copy_Menu)

        # Get list of clipboard items (that are complete clips or transitions)
        # i.e. ignore partial clipboard items (keyframes / effects / etc...)
        clipboard_clip_ids = [k for k, v in self.copy_clipboard.items() if v.get('id')]
        clipboard_tran_ids = [k for k, v in self.copy_transition_clipboard.items() if v.get('id')]
        # Determine if the paste menu should be shown
        if self.copy_clipboard and len(clipboard_clip_ids) + len(clipboard_tran_ids) == 0:
            # Paste Menu (Only show if partial clipboard available)
            Paste_Clip = menu.addAction(_("Paste"))
            Paste_Clip.triggered.connect(partial(self.Paste_Triggered, MENU_PASTE, 0.0, 0, clip_ids, []))

        menu.addSeparator()

        # Alignment Menu (if multiple selections)
        if len(clip_ids) > 1:
            Alignment_Menu = QMenu(_("Align"), self)
            Align_Left = Alignment_Menu.addAction(_("Left"))
            Align_Left.triggered.connect(partial(self.Align_Triggered, MENU_ALIGN_LEFT, clip_ids, tran_ids))
            Align_Right = Alignment_Menu.addAction(_("Right"))
            Align_Right.triggered.connect(partial(self.Align_Triggered, MENU_ALIGN_RIGHT, clip_ids, tran_ids))

            # Add menu to parent
            menu.addMenu(Alignment_Menu)

        # Fade In Menu
        Fade_Menu = QMenu(_("Fade"), self)
        Fade_None = Fade_Menu.addAction(_("No Fade"))
        Fade_None.triggered.connect(partial(self.Fade_Triggered, MENU_FADE_NONE, clip_ids))
        Fade_Menu.addSeparator()
        for position in ["Start of Clip", "End of Clip", "Entire Clip"]:
            Position_Menu = QMenu(_(position), self)

            if position == "Start of Clip":
                Fade_In_Fast = Position_Menu.addAction(_("Fade In (Fast)"))
                Fade_In_Fast.triggered.connect(partial(self.Fade_Triggered, MENU_FADE_IN_FAST, clip_ids, position))
                Fade_In_Slow = Position_Menu.addAction(_("Fade In (Slow)"))
                Fade_In_Slow.triggered.connect(partial(self.Fade_Triggered, MENU_FADE_IN_SLOW, clip_ids, position))

            elif position == "End of Clip":
                Fade_Out_Fast = Position_Menu.addAction(_("Fade Out (Fast)"))
                Fade_Out_Fast.triggered.connect(partial(self.Fade_Triggered, MENU_FADE_OUT_FAST, clip_ids, position))
                Fade_Out_Slow = Position_Menu.addAction(_("Fade Out (Slow)"))
                Fade_Out_Slow.triggered.connect(partial(self.Fade_Triggered, MENU_FADE_OUT_SLOW, clip_ids, position))

            else:
                Fade_In_Out_Fast = Position_Menu.addAction(_("Fade In and Out (Fast)"))
                Fade_In_Out_Fast.triggered.connect(partial(self.Fade_Triggered, MENU_FADE_IN_OUT_FAST, clip_ids, position))
                Fade_In_Out_Slow = Position_Menu.addAction(_("Fade In and Out (Slow)"))
                Fade_In_Out_Slow.triggered.connect(partial(self.Fade_Triggered, MENU_FADE_IN_OUT_SLOW, clip_ids, position))
                Position_Menu.addSeparator()
                Fade_In_Slow = Position_Menu.addAction(_("Fade In (Entire Clip)"))
                Fade_In_Slow.triggered.connect(partial(self.Fade_Triggered, MENU_FADE_IN_SLOW, clip_ids, position))
                Fade_Out_Slow = Position_Menu.addAction(_("Fade Out (Entire Clip)"))
                Fade_Out_Slow.triggered.connect(partial(self.Fade_Triggered, MENU_FADE_OUT_SLOW, clip_ids, position))

            Fade_Menu.addMenu(Position_Menu)
        menu.addMenu(Fade_Menu)


        # Animate Menu
        Animate_Menu = QMenu(_("Animate"), self)
        Animate_None = Animate_Menu.addAction(_("No Animation"))
        Animate_None.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_NONE, clip_ids))
        Animate_Menu.addSeparator()
        for position in ["Start of Clip", "End of Clip", "Entire Clip"]:
            Position_Menu = QMenu(_(position), self)

            # Scale
            Scale_Menu = QMenu(_("Zoom"), self)
            Animate_In_50_100 = Scale_Menu.addAction(_("Zoom In (50% to 100%)"))
            Animate_In_50_100.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_IN_50_100, clip_ids, position))
            Animate_In_75_100 = Scale_Menu.addAction(_("Zoom In (75% to 100%)"))
            Animate_In_75_100.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_IN_75_100, clip_ids, position))
            Animate_In_100_150 = Scale_Menu.addAction(_("Zoom In (100% to 150%)"))
            Animate_In_100_150.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_IN_100_150, clip_ids, position))
            Animate_Out_100_75 = Scale_Menu.addAction(_("Zoom Out (100% to 75%)"))
            Animate_Out_100_75.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_OUT_100_75, clip_ids, position))
            Animate_Out_100_50 = Scale_Menu.addAction(_("Zoom Out (100% to 50%)"))
            Animate_Out_100_50.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_OUT_100_50, clip_ids, position))
            Animate_Out_150_100 = Scale_Menu.addAction(_("Zoom Out (150% to 100%)"))
            Animate_Out_150_100.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_OUT_150_100, clip_ids, position))
            Position_Menu.addMenu(Scale_Menu)

            # Center to Edge
            Center_Edge_Menu = QMenu(_("Center to Edge"), self)
            Animate_Center_Top = Center_Edge_Menu.addAction(_("Center to Top"))
            Animate_Center_Top.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_CENTER_TOP, clip_ids, position))
            Animate_Center_Left = Center_Edge_Menu.addAction(_("Center to Left"))
            Animate_Center_Left.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_CENTER_LEFT, clip_ids, position))
            Animate_Center_Right = Center_Edge_Menu.addAction(_("Center to Right"))
            Animate_Center_Right.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_CENTER_RIGHT, clip_ids, position))
            Animate_Center_Bottom = Center_Edge_Menu.addAction(_("Center to Bottom"))
            Animate_Center_Bottom.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_CENTER_BOTTOM, clip_ids, position))
            Position_Menu.addMenu(Center_Edge_Menu)

            # Edge to Center
            Edge_Center_Menu = QMenu(_("Edge to Center"), self)
            Animate_Top_Center = Edge_Center_Menu.addAction(_("Top to Center"))
            Animate_Top_Center.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_TOP_CENTER, clip_ids, position))
            Animate_Left_Center = Edge_Center_Menu.addAction(_("Left to Center"))
            Animate_Left_Center.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_LEFT_CENTER, clip_ids, position))
            Animate_Right_Center = Edge_Center_Menu.addAction(_("Right to Center"))
            Animate_Right_Center.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_RIGHT_CENTER, clip_ids, position))
            Animate_Bottom_Center = Edge_Center_Menu.addAction(_("Bottom to Center"))
            Animate_Bottom_Center.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_BOTTOM_CENTER, clip_ids, position))
            Position_Menu.addMenu(Edge_Center_Menu)

            # Edge to Edge
            Edge_Edge_Menu = QMenu(_("Edge to Edge"), self)
            Animate_Top_Bottom = Edge_Edge_Menu.addAction(_("Top to Bottom"))
            Animate_Top_Bottom.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_TOP_BOTTOM, clip_ids, position))
            Animate_Left_Right = Edge_Edge_Menu.addAction(_("Left to Right"))
            Animate_Left_Right.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_LEFT_RIGHT, clip_ids, position))
            Animate_Right_Left = Edge_Edge_Menu.addAction(_("Right to Left"))
            Animate_Right_Left.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_RIGHT_LEFT, clip_ids, position))
            Animate_Bottom_Top = Edge_Edge_Menu.addAction(_("Bottom to Top"))
            Animate_Bottom_Top.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_BOTTOM_TOP, clip_ids, position))
            Position_Menu.addMenu(Edge_Edge_Menu)

            # Random Animation
            Position_Menu.addSeparator()
            Random = Position_Menu.addAction(_("Random"))
            Random.triggered.connect(partial(self.Animate_Triggered, MENU_ANIMATE_RANDOM, clip_ids, position))

            # Add Sub-Menu's to Position menu
            Animate_Menu.addMenu(Position_Menu)

        # Add Each position menu
        menu.addMenu(Animate_Menu)

        # Rotate Menu
        Rotation_Menu = QMenu(_("Rotate"), self)
        Rotation_None = Rotation_Menu.addAction(_("No Rotation"))
        Rotation_None.triggered.connect(partial(self.Rotate_Triggered, MENU_ROTATE_NONE, clip_ids))
        Rotation_Menu.addSeparator()
        Rotation_90_Right = Rotation_Menu.addAction(_("Rotate 90 (Right)"))
        Rotation_90_Right.triggered.connect(partial(self.Rotate_Triggered, MENU_ROTATE_90_RIGHT, clip_ids))
        Rotation_90_Left = Rotation_Menu.addAction(_("Rotate 90 (Left)"))
        Rotation_90_Left.triggered.connect(partial(self.Rotate_Triggered, MENU_ROTATE_90_LEFT, clip_ids))
        Rotation_180_Flip = Rotation_Menu.addAction(_("Rotate 180 (Flip)"))
        Rotation_180_Flip.triggered.connect(partial(self.Rotate_Triggered, MENU_ROTATE_180_FLIP, clip_ids))
        menu.addMenu(Rotation_Menu)

        # Layout Menu
        Layout_Menu = QMenu(_("Layout"), self)
        Layout_None = Layout_Menu.addAction(_("Reset Layout"))
        Layout_None.triggered.connect(partial(self.Layout_Triggered, MENU_LAYOUT_NONE, clip_ids))
        Layout_Menu.addSeparator()
        Layout_Center = Layout_Menu.addAction(_("1/4 Size - Center"))
        Layout_Center.triggered.connect(partial(self.Layout_Triggered, MENU_LAYOUT_CENTER, clip_ids))
        Layout_Top_Left = Layout_Menu.addAction(_("1/4 Size - Top Left"))
        Layout_Top_Left.triggered.connect(partial(self.Layout_Triggered, MENU_LAYOUT_TOP_LEFT, clip_ids))
        Layout_Top_Right = Layout_Menu.addAction(_("1/4 Size - Top Right"))
        Layout_Top_Right.triggered.connect(partial(self.Layout_Triggered, MENU_LAYOUT_TOP_RIGHT, clip_ids))
        Layout_Bottom_Left = Layout_Menu.addAction(_("1/4 Size - Bottom Left"))
        Layout_Bottom_Left.triggered.connect(partial(self.Layout_Triggered, MENU_LAYOUT_BOTTOM_LEFT, clip_ids))
        Layout_Bottom_Right = Layout_Menu.addAction(_("1/4 Size - Bottom Right"))
        Layout_Bottom_Right.triggered.connect(partial(self.Layout_Triggered, MENU_LAYOUT_BOTTOM_RIGHT, clip_ids))
        Layout_Menu.addSeparator()
        Layout_Bottom_All_With_Aspect = Layout_Menu.addAction(_("Show All (Maintain Ratio)"))
        Layout_Bottom_All_With_Aspect.triggered.connect(partial(self.Layout_Triggered, MENU_LAYOUT_ALL_WITH_ASPECT, clip_ids))
        Layout_Bottom_All_Without_Aspect = Layout_Menu.addAction(_("Show All (Distort)"))
        Layout_Bottom_All_Without_Aspect.triggered.connect(partial(self.Layout_Triggered, MENU_LAYOUT_ALL_WITHOUT_ASPECT, clip_ids))
        menu.addMenu(Layout_Menu)

        # Time Menu
        Time_Menu = QMenu(_("Time"), self)
        Time_None = Time_Menu.addAction(_("Reset Time"))
        Time_None.triggered.connect(partial(self.Time_Triggered, MENU_TIME_NONE, clip_ids, '1X'))
        Time_Menu.addSeparator()
        for speed, speed_values in [("Normal", ['1X']), ("Fast", ['2X', '4X', '8X', '16X', '32X']), ("Slow", ['1/2X', '1/4X', '1/8X', '1/16X', '1/32X'])]:
            Speed_Menu = QMenu(_(speed), self)

            for direction, direction_value in [("Forward", MENU_TIME_FORWARD), ("Backward", MENU_TIME_BACKWARD)]:
                Direction_Menu = QMenu(_(direction), self)

                for actual_speed in speed_values:
                    # Add menu option
                    Time_Option = Direction_Menu.addAction(_(actual_speed))
                    Time_Option.triggered.connect(partial(self.Time_Triggered, direction_value, clip_ids, actual_speed))

                # Add menu to parent
                Speed_Menu.addMenu(Direction_Menu)
            # Add menu to parent
            Time_Menu.addMenu(Speed_Menu)

        # Add menu to parent
        menu.addMenu(Time_Menu)

        # Volume Menu
        Volume_Menu = QMenu(_("Volume"), self)
        Volume_None = Volume_Menu.addAction(_("Reset Volume"))
        Volume_None.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_NONE, clip_ids))
        Volume_Menu.addSeparator()
        for position in ["Start of Clip", "End of Clip", "Entire Clip"]:
            Position_Menu = QMenu(_(position), self)

            if position == "Start of Clip":
                Fade_In_Fast = Position_Menu.addAction(_("Fade In (Fast)"))
                Fade_In_Fast.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_FADE_IN_FAST, clip_ids, position))
                Fade_In_Slow = Position_Menu.addAction(_("Fade In (Slow)"))
                Fade_In_Slow.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_FADE_IN_SLOW, clip_ids, position))

            elif position == "End of Clip":
                Fade_Out_Fast = Position_Menu.addAction(_("Fade Out (Fast)"))
                Fade_Out_Fast.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_FADE_OUT_FAST, clip_ids, position))
                Fade_Out_Slow = Position_Menu.addAction(_("Fade Out (Slow)"))
                Fade_Out_Slow.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_FADE_OUT_SLOW, clip_ids, position))

            else:
                Fade_In_Out_Fast = Position_Menu.addAction(_("Fade In and Out (Fast)"))
                Fade_In_Out_Fast.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_FADE_IN_OUT_FAST, clip_ids, position))
                Fade_In_Out_Slow = Position_Menu.addAction(_("Fade In and Out (Slow)"))
                Fade_In_Out_Slow.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_FADE_IN_OUT_SLOW, clip_ids, position))
                Position_Menu.addSeparator()
                Fade_In_Slow = Position_Menu.addAction(_("Fade In (Entire Clip)"))
                Fade_In_Slow.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_FADE_IN_SLOW, clip_ids, position))
                Fade_Out_Slow = Position_Menu.addAction(_("Fade Out (Entire Clip)"))
                Fade_Out_Slow.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_FADE_OUT_SLOW, clip_ids, position))

            # Add levels (100% to 0%)
            Position_Menu.addSeparator()
            Volume_100 = Position_Menu.addAction(_("Level 100%"))
            Volume_100.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_100, clip_ids, position))
            Volume_90 = Position_Menu.addAction(_("Level 90%"))
            Volume_90.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_90, clip_ids, position))
            Volume_80 = Position_Menu.addAction(_("Level 80%"))
            Volume_80.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_80, clip_ids, position))
            Volume_70 = Position_Menu.addAction(_("Level 70%"))
            Volume_70.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_70, clip_ids, position))
            Volume_60 = Position_Menu.addAction(_("Level 60%"))
            Volume_60.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_60, clip_ids, position))
            Volume_50 = Position_Menu.addAction(_("Level 50%"))
            Volume_50.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_50, clip_ids, position))
            Volume_40 = Position_Menu.addAction(_("Level 40%"))
            Volume_40.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_40, clip_ids, position))
            Volume_30 = Position_Menu.addAction(_("Level 30%"))
            Volume_30.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_30, clip_ids, position))
            Volume_20 = Position_Menu.addAction(_("Level 20%"))
            Volume_20.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_20, clip_ids, position))
            Volume_10 = Position_Menu.addAction(_("Level 10%"))
            Volume_10.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_10, clip_ids, position))
            Volume_0 = Position_Menu.addAction(_("Level 0%"))
            Volume_0.triggered.connect(partial(self.Volume_Triggered, MENU_VOLUME_LEVEL_0, clip_ids, position))

            Volume_Menu.addMenu(Position_Menu)
        menu.addMenu(Volume_Menu)

        # Add separate audio menu
        Split_Audio_Channels_Menu = QMenu(_("Separate Audio"), self)
        Split_Single_Clip = Split_Audio_Channels_Menu.addAction(_("Single Clip (all channels)"))
        Split_Single_Clip.triggered.connect(partial(self.Split_Audio_Triggered, MENU_SPLIT_AUDIO_SINGLE, clip_ids))
        Split_Multiple_Clips = Split_Audio_Channels_Menu.addAction(_("Multiple Clips (each channel)"))
        Split_Multiple_Clips.triggered.connect(partial(self.Split_Audio_Triggered, MENU_SPLIT_AUDIO_MULTIPLE, clip_ids))
        menu.addMenu(Split_Audio_Channels_Menu)

        # If Playhead overlapping clip
        if clip:
            start_of_clip = float(clip.data["start"])
            end_of_clip = float(clip.data["end"])
            position_of_clip = float(clip.data["position"])
            if playhead_position >= position_of_clip and playhead_position <= (position_of_clip + (end_of_clip - start_of_clip)):
                # Add split clip menu
                Slice_Menu = QMenu(_("Slice"), self)
                Slice_Keep_Both = Slice_Menu.addAction(_("Keep Both Sides"))
                Slice_Keep_Both.setShortcut(QKeySequence(self.window.getShortcutByName("sliceAllKeepBothSides")))
                Slice_Keep_Both.triggered.connect(partial(self.Slice_Triggered, MENU_SLICE_KEEP_BOTH, [clip_id], [], playhead_position))
                Slice_Keep_Left = Slice_Menu.addAction(_("Keep Left Side"))
                Slice_Keep_Left.setShortcut(QKeySequence(self.window.getShortcutByName("sliceAllKeepLeftSide")))
                Slice_Keep_Left.triggered.connect(partial(self.Slice_Triggered, MENU_SLICE_KEEP_LEFT, [clip_id], [], playhead_position))
                Slice_Keep_Right = Slice_Menu.addAction(_("Keep Right Side"))
                Slice_Keep_Right.setShortcut(QKeySequence(self.window.getShortcutByName("sliceAllKeepRightSide")))
                Slice_Keep_Right.triggered.connect(partial(self.Slice_Triggered, MENU_SLICE_KEEP_RIGHT, [clip_id], [], playhead_position))
                menu.addMenu(Slice_Menu)

        # Transform menu
        Transform_Action = self.window.actionTransform
        Transform_Action.triggered.connect(partial(self.Transform_Triggered, MENU_TRANSFORM, clip_ids))
        menu.addAction(Transform_Action)

        # Add clip display menu (waveform or thunbnail)
        menu.addSeparator()
        Waveform_Menu = QMenu(_("Display"), self)
        ShowWaveform = Waveform_Menu.addAction(_("Show Waveform"))
        ShowWaveform.triggered.connect(partial(self.Show_Waveform_Triggered, clip_ids))
        HideWaveform = Waveform_Menu.addAction(_("Show Thumbnail"))
        HideWaveform.triggered.connect(partial(self.Hide_Waveform_Triggered, clip_ids))
        menu.addMenu(Waveform_Menu)

        # Properties
        menu.addAction(self.window.actionProperties)

        # Remove Clip Menu
        menu.addSeparator()
        menu.addAction(self.window.actionRemoveClip)

        # Show Context menu
        return menu.popup(QCursor.pos())

    def Transform_Triggered(self, action, clip_ids):
        print("Transform_Triggered")

        # Emit signal to transform this clip (for the 1st clip id)
        if clip_ids:
            # Transform first clip in list
            get_app().window.TransformSignal.emit(clip_ids[0])
        else:
            # Clear transform
            get_app().window.TransformSignal.emit("")

    def Show_Waveform_Triggered(self, clip_ids):
        """Show a waveform for the selected clip"""

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            file_path = clip.data["reader"]["path"]

            # Find actual clip object from libopenshot
            c = None
            clips = get_app().window.timeline_sync.timeline.Clips()
            for clip_object in clips:
                if clip_object.Id() == clip_id:
                    c = clip_object

            if c and c.Reader() and not c.Reader().info.has_single_image:
                # Find frame 1 channel_filter property
                channel_filter = c.channel_filter.GetInt(1)

                # Set cursor to waiting
                get_app().setOverrideCursor(QCursor(Qt.WaitCursor))

                # Get audio data in a separate thread (so it doesn't block the UI)
                channel_filter = channel_filter
                get_audio_data(clip_id, file_path, channel_filter, c.volume)

    def Hide_Waveform_Triggered(self, clip_ids):
        """Hide the waveform for the selected clip"""

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)

            # Pass to javascript timeline (and render)
            cmd = JS_SCOPE_SELECTOR + ".hideAudioData('" + clip_id + "');"
            self.page().mainFrame().evaluateJavaScript(cmd)

    def Waveform_Ready(self, clip_id, audio_data):
        """Callback when audio waveform is ready"""
        log.info("Waveform_Ready for clip ID: %s" % (clip_id))

        # Convert waveform data to JSON
        serialized_audio_data = json.dumps(audio_data)

        # Pass to javascript timeline (and render)
        cmd = JS_SCOPE_SELECTOR + ".setAudioData('" + clip_id + "', " + serialized_audio_data + ");"
        self.page().mainFrame().evaluateJavaScript(cmd)

        # Restore normal cursor
        get_app().restoreOverrideCursor()

    def Split_Audio_Triggered(self, action, clip_ids):
        """Callback for split audio context menus"""
        log.info("Split_Audio_Triggered")

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)

            # Filter out audio on the original clip
            p = openshot.Point(1, 0.0, openshot.CONSTANT) # Override has_audio keyframe to False
            p_object = json.loads(p.Json())
            clip.data["has_audio"] = { "Points" : [p_object]}

            # Save filter on original clip
            clip.save()

            # Clear audio override
            p = openshot.Point(1, -1.0, openshot.CONSTANT) # Override has_audio keyframe to False
            p_object = json.loads(p.Json())
            clip.data["has_audio"] = { "Points" : [p_object]}

            # Remove the ID property from the clip (so it becomes a new one)
            clip.id = None
            clip.type = 'insert'
            clip.data.pop('id')
            clip.key.pop(1)

            if action == MENU_SPLIT_AUDIO_SINGLE:
                # Clear channel filter on new clip
                p = openshot.Point(1, -1.0, openshot.CONSTANT)
                p_object = json.loads(p.Json())
                clip.data["channel_filter"] = { "Points" : [p_object]}

                # Filter out video on the new clip
                p = openshot.Point(1, 0.0, openshot.CONSTANT) # Override has_audio keyframe to False
                p_object = json.loads(p.Json())
                clip.data["has_video"] = { "Points" : [p_object]}

                # Adjust the layer, so this new audio clip doesn't overlap the parent
                clip.data['layer'] = clip.data['layer'] - 1 # Add to layer below clip

                # Save changes
                clip.save()

                # Generate waveform for clip
                self.Show_Waveform_Triggered([clip.id])

            if action == MENU_SPLIT_AUDIO_MULTIPLE:
                # Get # of channels on clip
                channels = int(clip.data["reader"]["channels"])

                # Loop through each channel
                for channel in range(0, channels):
                    log.info("Adding clip for channel %s" % channel)

                    # Each clip is filtered to a different channel
                    p = openshot.Point(1, channel, openshot.CONSTANT)
                    p_object = json.loads(p.Json())
                    clip.data["channel_filter"] = { "Points" : [p_object]}

                    # Filter out video on the new clip
                    p = openshot.Point(1, 0.0, openshot.CONSTANT) # Override has_audio keyframe to False
                    p_object = json.loads(p.Json())
                    clip.data["has_video"] = { "Points" : [p_object]}

                    # Adjust the layer, so this new audio clip doesn't overlap the parent
                    clip.data['layer'] = max(clip.data['layer'] - 1, 0) # Add to layer below clip

                    # Save changes
                    clip.save()

                    # Generate waveform for clip
                    self.Show_Waveform_Triggered([clip.id])

                    # Remove the ID property from the clip (so next time, it will create a new clip)
                    clip.id = None
                    clip.type = 'insert'
                    clip.data.pop('id')

    def Layout_Triggered(self, action, clip_ids):
        """Callback for the layout context menus"""
        log.info(action)

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)

            new_gravity = openshot.GRAVITY_CENTER
            if action == MENU_LAYOUT_CENTER:
                new_gravity = openshot.GRAVITY_CENTER
            if action == MENU_LAYOUT_TOP_LEFT:
                new_gravity = openshot.GRAVITY_TOP_LEFT
            elif action == MENU_LAYOUT_TOP_RIGHT:
                new_gravity = openshot.GRAVITY_TOP_RIGHT
            elif action == MENU_LAYOUT_BOTTOM_LEFT:
                new_gravity = openshot.GRAVITY_BOTTOM_LEFT
            elif action == MENU_LAYOUT_BOTTOM_RIGHT:
                new_gravity = openshot.GRAVITY_BOTTOM_RIGHT

            if action == MENU_LAYOUT_NONE:
                # Reset scale mode
                clip.data["scale"] = openshot.SCALE_FIT
                clip.data["gravity"] = openshot.GRAVITY_CENTER

                # Clear scale keyframes
                p = openshot.Point(1, 1.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data["scale_x"] = { "Points" : [p_object]}
                clip.data["scale_y"] = { "Points" : [p_object]}

                # Clear location keyframes
                p = openshot.Point(1, 0.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data["location_x"] = { "Points" : [p_object]}
                clip.data["location_y"] = { "Points" : [p_object]}

            if action == MENU_LAYOUT_CENTER or \
                   action == MENU_LAYOUT_TOP_LEFT or \
                   action == MENU_LAYOUT_TOP_RIGHT or \
                   action == MENU_LAYOUT_BOTTOM_LEFT or \
                   action == MENU_LAYOUT_BOTTOM_RIGHT:
                # Reset scale mode
                clip.data["scale"] = openshot.SCALE_FIT
                clip.data["gravity"] = new_gravity

                # Add scale keyframes
                p = openshot.Point(1, 0.5, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data["scale_x"] = { "Points" : [p_object]}
                clip.data["scale_y"] = { "Points" : [p_object]}

                # Add location keyframes
                p = openshot.Point(1, 0.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data["location_x"] = { "Points" : [p_object]}
                clip.data["location_y"] = { "Points" : [p_object]}


            if action == MENU_LAYOUT_ALL_WITH_ASPECT:
                # Update all intersecting clips
                self.show_all_clips(clip, False)

            elif action == MENU_LAYOUT_ALL_WITHOUT_ASPECT:
                # Update all intersecting clips
                self.show_all_clips(clip, True)

            else:
                # Save changes
                self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

    def Animate_Triggered(self, action, clip_ids, position="Entire Clip"):
        """Callback for the animate context menus"""
        log.info(action)

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)

            # Get framerate
            fps = get_app().project.get(["fps"])
            fps_float = float(fps["num"]) / float(fps["den"])

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            start_of_clip = round(float(clip.data["start"]) * fps_float) + 1
            end_of_clip = round(float(clip.data["end"]) * fps_float) + 1

            # Determine the beginning and ending of this animation
            # ["Start of Clip", "End of Clip", "Entire Clip"]
            start_animation = start_of_clip
            end_animation = end_of_clip
            if position == "Start of Clip":
                start_animation = start_of_clip
                end_animation = min(start_of_clip + (1.0 * fps_float), end_of_clip)
            elif position == "End of Clip":
                start_animation = max(1.0, end_of_clip - (1.0 * fps_float))
                end_animation = end_of_clip

            if action == MENU_ANIMATE_NONE:
                # Clear all keyframes
                default_zoom = openshot.Point(start_animation, 1.0, openshot.BEZIER)
                default_zoom_object = json.loads(default_zoom.Json())
                default_loc = openshot.Point(start_animation, 0.0, openshot.BEZIER)
                default_loc_object = json.loads(default_loc.Json())
                clip.data["gravity"] = openshot.GRAVITY_CENTER
                clip.data["scale_x"] = { "Points" : [default_zoom_object]}
                clip.data["scale_y"] = { "Points" : [default_zoom_object]}
                clip.data["location_x"] = { "Points" : [default_loc_object]}
                clip.data["location_y"] = { "Points" : [default_loc_object]}

            if action in [MENU_ANIMATE_IN_50_100, MENU_ANIMATE_IN_75_100, MENU_ANIMATE_IN_100_150, MENU_ANIMATE_OUT_100_75, MENU_ANIMATE_OUT_100_50, MENU_ANIMATE_OUT_150_100]:
                # Scale animation
                start_scale = 1.0
                end_scale = 1.0
                if action == MENU_ANIMATE_IN_50_100:
                    start_scale = 0.5
                elif action == MENU_ANIMATE_IN_75_100:
                    start_scale = 0.75
                elif action == MENU_ANIMATE_IN_100_150:
                    end_scale = 1.5
                elif action == MENU_ANIMATE_OUT_100_75:
                    end_scale = 0.75
                elif action == MENU_ANIMATE_OUT_100_50:
                    end_scale = 0.5
                elif action == MENU_ANIMATE_OUT_150_100:
                    start_scale = 1.5

                # Add keyframes
                start = openshot.Point(start_animation, start_scale, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, end_scale, openshot.BEZIER)
                end_object = json.loads(end.Json())
                clip.data["gravity"] = openshot.GRAVITY_CENTER
                clip.data["scale_x"]["Points"].append(start_object)
                clip.data["scale_x"]["Points"].append(end_object)
                clip.data["scale_y"]["Points"].append(start_object)
                clip.data["scale_y"]["Points"].append(end_object)


            if action in [MENU_ANIMATE_CENTER_TOP, MENU_ANIMATE_CENTER_LEFT, MENU_ANIMATE_CENTER_RIGHT, MENU_ANIMATE_CENTER_BOTTOM,
                          MENU_ANIMATE_TOP_CENTER, MENU_ANIMATE_LEFT_CENTER, MENU_ANIMATE_RIGHT_CENTER, MENU_ANIMATE_BOTTOM_CENTER,
                          MENU_ANIMATE_TOP_BOTTOM, MENU_ANIMATE_LEFT_RIGHT, MENU_ANIMATE_RIGHT_LEFT, MENU_ANIMATE_BOTTOM_TOP]:
                # Location animation
                animate_start_x = 0.0
                animate_end_x = 0.0
                animate_start_y = 0.0
                animate_end_y = 0.0
                # Center to edge...
                if action == MENU_ANIMATE_CENTER_TOP:
                    animate_end_y = -1.0
                elif action == MENU_ANIMATE_CENTER_LEFT:
                    animate_end_x = -1.0
                elif action == MENU_ANIMATE_CENTER_RIGHT:
                    animate_end_x = 1.0
                elif action == MENU_ANIMATE_CENTER_BOTTOM:
                    animate_end_y = 1.0

                # Edge to Center
                elif action == MENU_ANIMATE_TOP_CENTER:
                    animate_start_y = -1.0
                elif action == MENU_ANIMATE_LEFT_CENTER:
                    animate_start_x = -1.0
                elif action == MENU_ANIMATE_RIGHT_CENTER:
                    animate_start_x = 1.0
                elif action == MENU_ANIMATE_BOTTOM_CENTER:
                    animate_start_y = 1.0

                # Edge to Edge
                elif action == MENU_ANIMATE_TOP_BOTTOM:
                    animate_start_y = -1.0
                    animate_end_y = 1.0
                elif action == MENU_ANIMATE_LEFT_RIGHT:
                    animate_start_x = -1.0
                    animate_end_x = 1.0
                elif action == MENU_ANIMATE_RIGHT_LEFT:
                    animate_start_x = 1.0
                    animate_end_x = -1.0
                elif action == MENU_ANIMATE_BOTTOM_TOP:
                    animate_start_y = 1.0
                    animate_end_y = -1.0

                # Add keyframes
                start_x = openshot.Point(start_animation, animate_start_x, openshot.BEZIER)
                start_x_object = json.loads(start_x.Json())
                end_x = openshot.Point(end_animation, animate_end_x, openshot.BEZIER)
                end_x_object = json.loads(end_x.Json())
                start_y = openshot.Point(start_animation, animate_start_y, openshot.BEZIER)
                start_y_object = json.loads(start_y.Json())
                end_y = openshot.Point(end_animation, animate_end_y, openshot.BEZIER)
                end_y_object = json.loads(end_y.Json())
                clip.data["gravity"] = openshot.GRAVITY_CENTER
                clip.data["location_x"]["Points"].append(start_x_object)
                clip.data["location_x"]["Points"].append(end_x_object)
                clip.data["location_y"]["Points"].append(start_y_object)
                clip.data["location_y"]["Points"].append(end_y_object)

            if action == MENU_ANIMATE_RANDOM:
                # Location animation
                animate_start_x = uniform(-0.5, 0.5)
                animate_end_x = uniform(-0.15, 0.15)
                animate_start_y = uniform(-0.5, 0.5)
                animate_end_y = uniform(-0.15, 0.15)

                # Scale animation
                start_scale = uniform(0.5, 1.5)
                end_scale = uniform(0.85, 1.15)

                # Add keyframes
                start = openshot.Point(start_animation, start_scale, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, end_scale, openshot.BEZIER)
                end_object = json.loads(end.Json())
                clip.data["gravity"] = openshot.GRAVITY_CENTER
                clip.data["scale_x"]["Points"].append(start_object)
                clip.data["scale_x"]["Points"].append(end_object)
                clip.data["scale_y"]["Points"].append(start_object)
                clip.data["scale_y"]["Points"].append(end_object)

                # Add keyframes
                start_x = openshot.Point(start_animation, animate_start_x, openshot.BEZIER)
                start_x_object = json.loads(start_x.Json())
                end_x = openshot.Point(end_animation, animate_end_x, openshot.BEZIER)
                end_x_object = json.loads(end_x.Json())
                start_y = openshot.Point(start_animation, animate_start_y, openshot.BEZIER)
                start_y_object = json.loads(start_y.Json())
                end_y = openshot.Point(end_animation, animate_end_y, openshot.BEZIER)
                end_y_object = json.loads(end_y.Json())
                clip.data["gravity"] = openshot.GRAVITY_CENTER
                clip.data["location_x"]["Points"].append(start_x_object)
                clip.data["location_x"]["Points"].append(end_x_object)
                clip.data["location_y"]["Points"].append(start_y_object)
                clip.data["location_y"]["Points"].append(end_y_object)

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

    def Copy_Triggered(self, action, clip_ids, tran_ids):
        """Callback for copy context menus"""
        log.info(action)

        # Empty previous clipboard
        self.copy_clipboard = {}
        self.copy_transition_clipboard = {}

        # Loop through clip objects
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            self.copy_clipboard[clip_id] = {}

            if action == MENU_COPY_CLIP or action == MENU_COPY_ALL:
                self.copy_clipboard[clip_id] = clip.data
            elif action == MENU_COPY_KEYFRAMES_ALL:
                self.copy_clipboard[clip_id]['alpha'] = clip.data['alpha']
                self.copy_clipboard[clip_id]['gravity'] = clip.data['gravity']
                self.copy_clipboard[clip_id]['scale_x'] = clip.data['scale_x']
                self.copy_clipboard[clip_id]['scale_y'] = clip.data['scale_y']
                self.copy_clipboard[clip_id]['rotation'] = clip.data['rotation']
                self.copy_clipboard[clip_id]['location_x'] = clip.data['location_x']
                self.copy_clipboard[clip_id]['location_y'] = clip.data['location_y']
                self.copy_clipboard[clip_id]['time'] = clip.data['time']
                self.copy_clipboard[clip_id]['volume'] = clip.data['volume']
            elif action == MENU_COPY_KEYFRAMES_ALPHA:
                self.copy_clipboard[clip_id]['alpha'] = clip.data['alpha']
            elif action == MENU_COPY_KEYFRAMES_SCALE:
                self.copy_clipboard[clip_id]['gravity'] = clip.data['gravity']
                self.copy_clipboard[clip_id]['scale_x'] = clip.data['scale_x']
                self.copy_clipboard[clip_id]['scale_y'] = clip.data['scale_y']
            elif action == MENU_COPY_KEYFRAMES_ROTATE:
                self.copy_clipboard[clip_id]['gravity'] = clip.data['gravity']
                self.copy_clipboard[clip_id]['rotation'] = clip.data['rotation']
            elif action == MENU_COPY_KEYFRAMES_LOCATION:
                self.copy_clipboard[clip_id]['gravity'] = clip.data['gravity']
                self.copy_clipboard[clip_id]['location_x'] = clip.data['location_x']
                self.copy_clipboard[clip_id]['location_y'] = clip.data['location_y']
            elif action == MENU_COPY_KEYFRAMES_TIME:
                self.copy_clipboard[clip_id]['time'] = clip.data['time']
            elif action == MENU_COPY_KEYFRAMES_VOLUME:
                self.copy_clipboard[clip_id]['volume'] = clip.data['volume']
            elif action == MENU_COPY_EFFECTS:
                self.copy_clipboard[clip_id]['effects'] = clip.data['effects']

        # Loop through transition objects
        for tran_id in tran_ids:

            # Get existing transition object
            tran = Transition.get(id=tran_id)
            self.copy_transition_clipboard[tran_id] = {}

            if action == MENU_COPY_TRANSITION or action == MENU_COPY_ALL:
                self.copy_transition_clipboard[tran_id] = tran.data
            elif action == MENU_COPY_KEYFRAMES_ALL:
                self.copy_transition_clipboard[tran_id]['brightness'] = tran.data['brightness']
                self.copy_transition_clipboard[tran_id]['contrast'] = tran.data['contrast']
            elif action == MENU_COPY_KEYFRAMES_BRIGHTNESS:
                self.copy_transition_clipboard[tran_id]['brightness'] = tran.data['brightness']
            elif action == MENU_COPY_KEYFRAMES_CONTRAST:
                self.copy_transition_clipboard[tran_id]['contrast'] = tran.data['contrast']

    def Paste_Triggered(self, action, position, layer_id, clip_ids, tran_ids):
        """Callback for paste context menus"""
        log.info(action)

        # Get list of clipboard items (that are complete clips or transitions)
        # i.e. ignore partial clipboard items (keyframes / effects / etc...)
        clipboard_clip_ids = [k for k, v in self.copy_clipboard.items() if v.get('id')]
        clipboard_tran_ids = [k for k, v in self.copy_transition_clipboard.items() if v.get('id')]

        # Determine left most copied clip, and top most track (the top left point of the copied objects)
        if len(clipboard_clip_ids) + len(clipboard_tran_ids):
            left_most_position = -1.0
            top_most_layer = -1
            # Loop through each copied clip (looking for top left point)
            for clip_id in clipboard_clip_ids:
                # Get existing clip object
                clip = Clip()
                clip.data = self.copy_clipboard.get(clip_id, {})
                if clip.data['position'] < left_most_position or left_most_position == -1.0:
                    left_most_position = clip.data['position']
                if clip.data['layer'] > top_most_layer or top_most_layer == -1.0:
                    top_most_layer = clip.data['layer']
            # Loop through each copied transition (looking for top left point)
            for tran_id in clipboard_tran_ids:
                # Get existing transition object
                tran = Transition()
                tran.data = self.copy_transition_clipboard.get(tran_id, {})
                if tran.data['position'] < left_most_position or left_most_position == -1.0:
                    left_most_position = tran.data['position']
                if tran.data['layer'] > top_most_layer or top_most_layer == -1.0:
                    top_most_layer = tran.data['layer']

            # Default layer if not known
            if layer_id == -1:
                layer_id = top_most_layer

            # Determine difference from top left and paste location
            position_diff = position - left_most_position
            layer_diff = layer_id - top_most_layer

            # Loop through each copied clip
            for clip_id in clipboard_clip_ids:
                # Get existing clip object
                clip = Clip()
                clip.data = self.copy_clipboard.get(clip_id, {})

                # Remove the ID property from the clip (so it becomes a new one)
                clip.type = 'insert'
                clip.data.pop('id')

                # Adjust the position and track
                clip.data['position'] += position_diff
                clip.data['layer'] += layer_diff

                # Save changes
                clip.save()

            # Loop through all copied transitions
            for tran_id in clipboard_tran_ids:
                # Get existing transition object
                tran = Transition()
                tran.data = self.copy_transition_clipboard.get(tran_id, {})

                # Remove the ID property from the transition (so it becomes a new one)
                tran.type = 'insert'
                tran.data.pop('id')

                # Adjust the position and track
                tran.data['position'] += position_diff
                tran.data['layer'] += layer_diff

                # Save changes
                tran.save()

        # Loop through each full clip object copied
        if self.copy_clipboard:
            for clip_id in clip_ids:

                # Get existing clip object
                clip = Clip.get(id=clip_id)

                # Apply clipboard to clip (there should only be a single key in this dict)
                for k,v in self.copy_clipboard[list(self.copy_clipboard)[0]].items():
                    if k != 'id':
                        # Overwrite clips propeties (which are in the clipboard)
                        clip.data[k] = v

                # Save changes
                clip.save()

        # Loop through each full transition object copied
        if self.copy_transition_clipboard:
            for tran_id in tran_ids:

                # Get existing transition object
                tran = Transition.get(id=tran_id)

                # Apply clipboard to transition (there should only be a single key in this dict)
                for k, v in self.copy_transition_clipboard[list(self.copy_transition_clipboard)[0]].items():
                    if k != 'id':
                        # Overwrite transition propeties (which are in the clipboard)
                        tran.data[k] = v

                # Save changes
                tran.save()

    def Align_Triggered(self, action, clip_ids, tran_ids):
        """Callback for alignment context menus"""
        log.info(action)
        prop_name = "position"
        left_edge = -1.0
        right_edge = -1.0

        # Loop through each selected clip (find furthest left and right edge)
        for clip_id in clip_ids:
            # Get existing clip object
            clip = Clip.get(id=clip_id)
            position = float(clip.data["position"])
            start_of_clip = float(clip.data["start"])
            end_of_clip = float(clip.data["end"])

            if position < left_edge or left_edge == -1.0:
                left_edge = position
            if position + (end_of_clip - start_of_clip) > right_edge or right_edge == -1.0:
                right_edge = position + (end_of_clip - start_of_clip)

        # Loop through each selected transition (find furthest left and right edge)
        for tran_id in tran_ids:
            # Get existing transition object
            tran = Transition.get(id=tran_id)
            position = float(tran.data["position"])
            start_of_tran = float(tran.data["start"])
            end_of_tran = float(tran.data["end"])

            if position < left_edge or left_edge == -1.0:
                left_edge = position
            if position + (end_of_tran - start_of_tran) > right_edge or right_edge == -1.0:
                right_edge = position + (end_of_tran - start_of_tran)


        # Loop through each selected clip (update position to align clips)
        for clip_id in clip_ids:
            # Get existing clip object
            clip = Clip.get(id=clip_id)

            if action == MENU_ALIGN_LEFT:
                clip.data['position'] = left_edge
            elif action == MENU_ALIGN_RIGHT:
                position = float(clip.data["position"])
                start_of_clip = float(clip.data["start"])
                end_of_clip = float(clip.data["end"])
                right_clip_edge = position + (end_of_clip - start_of_clip)

                clip.data['position'] = position + (right_edge - right_clip_edge)

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

        # Loop through each selected transition (update position to align clips)
        for tran_id in tran_ids:
            # Get existing transition object
            tran = Transition.get(id=tran_id)

            if action == MENU_ALIGN_LEFT:
                tran.data['position'] = left_edge
            elif action == MENU_ALIGN_RIGHT:
                position = float(tran.data["position"])
                start_of_tran = float(tran.data["start"])
                end_of_tran = float(tran.data["end"])
                right_tran_edge = position + (end_of_tran - start_of_tran)

                tran.data['position'] = position + (right_edge - right_tran_edge)

            # Save changes
            self.update_transition_data(tran.data, only_basic_props=False)

    def Fade_Triggered(self, action, clip_ids, position="Entire Clip"):
        """Callback for fade context menus"""
        log.info(action)
        prop_name = "alpha"

        # Get FPS from project
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            start_of_clip = round(float(clip.data["start"]) * fps_float) + 1
            end_of_clip = round(float(clip.data["end"]) * fps_float) + 1

            # Determine the beginning and ending of this animation
            # ["Start of Clip", "End of Clip", "Entire Clip"]
            start_animation = start_of_clip
            end_animation = end_of_clip
            if position == "Start of Clip" and action in [MENU_FADE_IN_FAST, MENU_FADE_OUT_FAST]:
                start_animation = start_of_clip
                end_animation = min(start_of_clip + (1.0 * fps_float), end_of_clip)
            elif position == "Start of Clip" and action in [MENU_FADE_IN_SLOW, MENU_FADE_OUT_SLOW]:
                start_animation = start_of_clip
                end_animation = min(start_of_clip + (3.0 * fps_float), end_of_clip)
            elif position == "End of Clip" and action in [MENU_FADE_IN_FAST, MENU_FADE_OUT_FAST]:
                start_animation = max(1.0, end_of_clip - (1.0 * fps_float))
                end_animation = end_of_clip
            elif position == "End of Clip" and action in [MENU_FADE_IN_SLOW, MENU_FADE_OUT_SLOW]:
                start_animation = max(1.0, end_of_clip - (3.0 * fps_float))
                end_animation = end_of_clip

            # Fade in and out (special case)
            if position == "Entire Clip" and action == MENU_FADE_IN_OUT_FAST:
                # Call this method for the start and end of the clip
                self.Fade_Triggered(MENU_FADE_IN_FAST, clip_ids, "Start of Clip")
                self.Fade_Triggered(MENU_FADE_OUT_FAST, clip_ids, "End of Clip")
                return
            elif position == "Entire Clip" and action == MENU_FADE_IN_OUT_SLOW:
                # Call this method for the start and end of the clip
                self.Fade_Triggered(MENU_FADE_IN_SLOW, clip_ids, "Start of Clip")
                self.Fade_Triggered(MENU_FADE_OUT_SLOW, clip_ids, "End of Clip")
                return

            if action == MENU_FADE_NONE:
                # Clear all keyframes
                p = openshot.Point(1, 1.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data[prop_name] = { "Points" : [p_object]}

            if action in [MENU_FADE_IN_FAST, MENU_FADE_IN_SLOW]:
                # Add keyframes
                start = openshot.Point(start_animation, 0.0, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, 1.0, openshot.BEZIER)
                end_object = json.loads(end.Json())
                clip.data[prop_name]["Points"].append(start_object)
                clip.data[prop_name]["Points"].append(end_object)

            if action in [MENU_FADE_OUT_FAST, MENU_FADE_OUT_SLOW]:
                # Add keyframes
                start = openshot.Point(start_animation, 1.0, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, 0.0, openshot.BEZIER)
                end_object = json.loads(end.Json())
                clip.data[prop_name]["Points"].append(start_object)
                clip.data[prop_name]["Points"].append(end_object)

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

    @pyqtSlot(str, str, float)
    def RazorSliceAtCursor(self, clip_id, trans_id, cursor_position):
        """Callback from javascript that the razor tool was clicked"""

        # Determine slice mode (keep both [default], keep left [shift], keep right [ctrl]
        slice_mode = MENU_SLICE_KEEP_BOTH
        if int(QCoreApplication.instance().keyboardModifiers() & Qt.ControlModifier) > 0:
            slice_mode = MENU_SLICE_KEEP_RIGHT
        elif int(QCoreApplication.instance().keyboardModifiers() & Qt.ShiftModifier) > 0:
            slice_mode = MENU_SLICE_KEEP_LEFT

        if clip_id:
            # Slice clip
            QTimer.singleShot(0, partial(self.Slice_Triggered, slice_mode, [clip_id], [], cursor_position))
        elif trans_id:
            # Slice transitions
            QTimer.singleShot(0, partial(self.Slice_Triggered, slice_mode, [], [trans_id], cursor_position))

    def Slice_Triggered(self, action, clip_ids, trans_ids, playhead_position=0):
        """Callback for slice context menus"""

        # Loop through each clip (using the list of ids)
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)

            # Determine if waveform needs to be redrawn
            has_audio_data = bool(self.eval_js(JS_SCOPE_SELECTOR + ".hasAudioData('" + clip_id + "');"))

            if action == MENU_SLICE_KEEP_LEFT or action == MENU_SLICE_KEEP_BOTH:
                # Get details of original clip
                position_of_clip = float(clip.data["position"])
                start_of_clip = float(clip.data["start"])

                # Set new 'end' of clip
                clip.data["end"] = start_of_clip + (playhead_position - position_of_clip)

            elif action == MENU_SLICE_KEEP_RIGHT:
                # Get details of original clip
                position_of_clip = float(clip.data["position"])
                start_of_clip = float(clip.data["start"])

                # Set new 'end' of clip
                clip.data["position"] = playhead_position
                clip.data["start"] = start_of_clip + (playhead_position - position_of_clip)

                # Update thumbnail for right clip (after the clip has been created)
                self.UpdateClipThumbnail(clip.data)

            if action == MENU_SLICE_KEEP_BOTH:
                # Add the 2nd clip (the right side, since the left side has already been adjusted above)
                # Get right side clip object
                right_clip = Clip.get(id=clip_id)

                # Remove the ID property from the clip (so it becomes a new one)
                right_clip.id = None
                right_clip.type = 'insert'
                right_clip.data.pop('id')
                right_clip.key.pop(1)

                # Get details of original clip
                position_of_clip = float(right_clip.data["position"])
                start_of_clip = float(right_clip.data["start"])

                # Set new 'end' of right_clip
                right_clip.data["position"] = playhead_position
                right_clip.data["start"] = start_of_clip + (playhead_position - position_of_clip)

                # Save changes
                right_clip.save()

                # Update thumbnail for right clip (after the clip has been created)
                self.UpdateClipThumbnail(right_clip.data)

                # Save changes again (with new thumbnail)
                self.update_clip_data(right_clip.data, only_basic_props=False, ignore_reader=True)

                if has_audio_data:
                    # Re-generate waveform since volume curve has changed
                    log.info("Generate right splice waveform for clip id: %s" % right_clip.id)
                    self.Show_Waveform_Triggered(right_clip.id)

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

            if has_audio_data:
                # Re-generate waveform since volume curve has changed
                log.info("Generate left splice waveform for clip id: %s" % clip.id)
                self.Show_Waveform_Triggered(clip.id)


        # Loop through each transition (using the list of ids)
        for trans_id in trans_ids:
            # Get existing transition object
            trans = Transition.get(id=trans_id)

            if action == MENU_SLICE_KEEP_LEFT or action == MENU_SLICE_KEEP_BOTH:
                # Get details of original transition
                position_of_tran = float(trans.data["position"])

                # Set new 'end' of transition
                trans.data["end"] = playhead_position - position_of_tran

            elif action == MENU_SLICE_KEEP_RIGHT:
                # Get details of transition clip
                position_of_tran = float(trans.data["position"])
                end_of_tran = float(trans.data["end"])

                # Set new 'end' of transition
                trans.data["position"] = playhead_position
                trans.data["end"] = end_of_tran - (playhead_position - position_of_tran)

            if action == MENU_SLICE_KEEP_BOTH:
                # Add the 2nd transition (the right side, since the left side has already been adjusted above)
                # Get right side transition object
                right_tran = Transition.get(id=trans_id)

                # Remove the ID property from the transition (so it becomes a new one)
                right_tran.id = None
                right_tran.type = 'insert'
                right_tran.data.pop('id')
                right_tran.key.pop(1)

                # Get details of original transition
                position_of_tran = float(right_tran.data["position"])
                end_of_tran = float(right_tran.data["end"])

                # Set new 'end' of right_tran
                right_tran.data["position"] = playhead_position
                right_tran.data["end"] = end_of_tran - (playhead_position - position_of_tran)

                # Save changes
                right_tran.save()

                # Save changes again (right side)
                self.update_transition_data(right_tran.data, only_basic_props=False)

            # Save changes (left side)
            self.update_transition_data(trans.data, only_basic_props=False)

    def Volume_Triggered(self, action, clip_ids, position="Entire Clip"):
        """Callback for volume context menus"""
        log.info(action)
        prop_name = "volume"

        # Get FPS from project
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)
            start_of_clip = round(float(clip.data["start"]) * fps_float) + 1
            end_of_clip = round(float(clip.data["end"]) * fps_float) + 1

            # Determine the beginning and ending of this animation
            # ["Start of Clip", "End of Clip", "Entire Clip"]
            start_animation = start_of_clip
            end_animation = end_of_clip
            if position == "Start of Clip" and action in [MENU_VOLUME_FADE_IN_FAST, MENU_VOLUME_FADE_OUT_FAST]:
                start_animation = start_of_clip
                end_animation = min(start_of_clip + (1.0 * fps_float), end_of_clip)
            elif position == "Start of Clip" and action in [MENU_VOLUME_FADE_IN_SLOW, MENU_VOLUME_FADE_OUT_SLOW]:
                start_animation = start_of_clip
                end_animation = min(start_of_clip + (3.0 * fps_float), end_of_clip)
            elif position == "End of Clip" and action in [MENU_VOLUME_FADE_IN_FAST, MENU_VOLUME_FADE_OUT_FAST]:
                start_animation = max(1.0, end_of_clip - (1.0 * fps_float))
                end_animation = end_of_clip
            elif position == "End of Clip" and action in [MENU_VOLUME_FADE_IN_SLOW, MENU_VOLUME_FADE_OUT_SLOW]:
                start_animation = max(1.0, end_of_clip - (3.0 * fps_float))
                end_animation = end_of_clip
            elif position == "Start of Clip":
                # Only used when setting levels (a single keyframe)
                start_animation = start_of_clip
                end_animation = start_of_clip
            elif position == "End of Clip":
                # Only used when setting levels (a single keyframe)
                start_animation = end_of_clip
                end_animation = end_of_clip

            # Fade in and out (special case)
            if position == "Entire Clip" and action == MENU_VOLUME_FADE_IN_OUT_FAST:
                # Call this method for the start and end of the clip
                self.Volume_Triggered(MENU_VOLUME_FADE_IN_FAST, clip_ids, "Start of Clip")
                self.Volume_Triggered(MENU_VOLUME_FADE_OUT_FAST, clip_ids, "End of Clip")
                return
            elif position == "Entire Clip" and action == MENU_VOLUME_FADE_IN_OUT_SLOW:
                # Call this method for the start and end of the clip
                self.Volume_Triggered(MENU_VOLUME_FADE_IN_SLOW, clip_ids, "Start of Clip")
                self.Volume_Triggered(MENU_VOLUME_FADE_OUT_SLOW, clip_ids, "End of Clip")
                return

            if action == MENU_VOLUME_NONE:
                # Clear all keyframes
                p = openshot.Point(1, 1.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data[prop_name] = { "Points" : [p_object]}

            if action in [MENU_VOLUME_FADE_IN_FAST, MENU_VOLUME_FADE_IN_SLOW]:
                # Add keyframes
                start = openshot.Point(start_animation, 0.0, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, 1.0, openshot.BEZIER)
                end_object = json.loads(end.Json())
                clip.data[prop_name]["Points"].append(start_object)
                clip.data[prop_name]["Points"].append(end_object)

            if action in [MENU_VOLUME_FADE_OUT_FAST, MENU_VOLUME_FADE_OUT_SLOW]:
                # Add keyframes
                start = openshot.Point(start_animation, 1.0, openshot.BEZIER)
                start_object = json.loads(start.Json())
                end = openshot.Point(end_animation, 0.0, openshot.BEZIER)
                end_object = json.loads(end.Json())
                clip.data[prop_name]["Points"].append(start_object)
                clip.data[prop_name]["Points"].append(end_object)

            if action in [MENU_VOLUME_LEVEL_100, MENU_VOLUME_LEVEL_90, MENU_VOLUME_LEVEL_80, MENU_VOLUME_LEVEL_70,
                          MENU_VOLUME_LEVEL_60, MENU_VOLUME_LEVEL_50, MENU_VOLUME_LEVEL_40, MENU_VOLUME_LEVEL_30,
                          MENU_VOLUME_LEVEL_20, MENU_VOLUME_LEVEL_10, MENU_VOLUME_LEVEL_0]:
                # Add keyframes
                p = openshot.Point(start_animation, float(action) / 100.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data[prop_name]["Points"].append(p_object)

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

            # Determine if waveform needs to be redrawn
            has_audio_data = bool(self.eval_js(JS_SCOPE_SELECTOR + ".hasAudioData('" + clip.id + "');"))
            if has_audio_data:
                # Re-generate waveform since volume curve has changed
                self.Show_Waveform_Triggered(clip.id)

    def Rotate_Triggered(self, action, clip_ids, position="Start of Clip"):
        """Callback for rotate context menus"""
        log.info(action)
        prop_name = "rotation"

        # Get FPS from project
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)

            if action == MENU_ROTATE_NONE:
                # Clear all keyframes
                p = openshot.Point(1, 0.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data[prop_name] = { "Points" : [p_object]}

            if action == MENU_ROTATE_90_RIGHT:
                # Add keyframes
                p = openshot.Point(1, 90.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data[prop_name] = { "Points" : [p_object]}

            if action == MENU_ROTATE_90_LEFT:
                # Add keyframes
                p = openshot.Point(1, -90.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data[prop_name] = { "Points" : [p_object]}

            if action == MENU_ROTATE_180_FLIP:
                # Add keyframes
                p = openshot.Point(1, 180.0, openshot.BEZIER)
                p_object = json.loads(p.Json())
                clip.data[prop_name] = { "Points" : [p_object]}

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

    def Time_Triggered(self, action, clip_ids, speed="1X"):
        """Callback for rotate context menus"""
        log.info(action)
        prop_name = "time"

        # Get FPS from project
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Loop through each selected clip
        for clip_id in clip_ids:

            # Get existing clip object
            clip = Clip.get(id=clip_id)

            # Determine the beginning and ending of this animation
            start_animation = 1

            # Calculate speed factor
            speed_label = speed.replace('X', '')
            speed_parts = speed_label.split('/')
            even_multiple = 1
            if len(speed_parts) == 2:
                speed_factor = float(speed_parts[0]) / float(speed_parts[1])
                even_multiple = int(speed_parts[1])
            else:
                speed_factor = float(speed_label)
                even_multiple = int(speed_factor)

            # Clear all keyframes
            p = openshot.Point(start_animation, 0.0, openshot.LINEAR)
            p_object = json.loads(p.Json())
            clip.data[prop_name] = { "Points" : [p_object]}

            # Reset original end & duration (if available)
            if "original_data" in clip.data.keys():
                clip.data["end"] = clip.data["original_data"]["end"]
                clip.data["duration"] = clip.data["original_data"]["duration"]
                clip.data["reader"]["video_length"] = clip.data["original_data"]["video_length"]
                clip.data.pop("original_data")

            # Get the ending frame
            end_of_clip = round(float(clip.data["end"]) * fps_float) + 1

            # Determine the beginning and ending of this animation
            start_animation = round(float(clip.data["start"]) * fps_float) + 1
            duration_animation = self.round_to_multiple(end_of_clip - start_animation, even_multiple)
            end_animation = start_animation + duration_animation

            if action == MENU_TIME_FORWARD:
                # Add keyframes
                start = openshot.Point(start_animation, start_animation, openshot.LINEAR)
                start_object = json.loads(start.Json())
                clip.data[prop_name] = { "Points" : [start_object]}
                end = openshot.Point(start_animation + (duration_animation / speed_factor), end_animation, openshot.LINEAR)
                end_object = json.loads(end.Json())
                clip.data[prop_name]["Points"].append(end_object)
                # Keep original 'end' and 'duration'
                if "original_data" not in clip.data.keys():
                    clip.data["original_data"] = { "end" : clip.data["end"],
                                                   "duration" : clip.data["duration"],
                                                   "video_length" : clip.data["reader"]["video_length"] }
                # Adjust end & duration
                clip.data["end"] = (start_animation + (duration_animation / speed_factor)) / fps_float
                clip.data["duration"] = self.round_to_multiple(clip.data["duration"] / speed_factor, even_multiple)
                clip.data["reader"]["video_length"] = str(self.round_to_multiple(float(clip.data["reader"]["video_length"]) / speed_factor, even_multiple))

            if action == MENU_TIME_BACKWARD:
                # Add keyframes
                start = openshot.Point(start_animation, end_animation, openshot.LINEAR)
                start_object = json.loads(start.Json())
                clip.data[prop_name] = { "Points" : [start_object]}
                end = openshot.Point(start_animation + (duration_animation / speed_factor), start_animation, openshot.LINEAR)
                end_object = json.loads(end.Json())
                clip.data[prop_name]["Points"].append(end_object)
                # Keep original 'end' and 'duration'
                if "original_data" not in clip.data.keys():
                    clip.data["original_data"] = { "end" : clip.data["end"],
                                                   "duration" : clip.data["duration"],
                                                   "video_length" : clip.data["reader"]["video_length"] }
                # Adjust end & duration
                clip.data["end"] = (start_animation + (duration_animation / speed_factor)) / fps_float
                clip.data["duration"] = self.round_to_multiple(clip.data["duration"] / speed_factor, even_multiple)
                clip.data["reader"]["video_length"] = str(self.round_to_multiple(float(clip.data["reader"]["video_length"]) / speed_factor, even_multiple))

            # Save changes
            self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

    def round_to_multiple(self, number, multiple):
        """Round this to the closest multiple of a given #"""
        return number - (number % multiple)

    def show_all_clips(self, clip, stretch=False):
        """ Show all clips at the same time (arranged col by col, row by row)  """
        from math import sqrt

        # Get list of nearby clips
        available_clips = []
        start_position = float(clip.data["position"])
        for c in Clip.filter():
            if float(c.data["position"]) >= (start_position - 0.5) and float(c.data["position"]) <= (start_position + 0.5):
                # add to list
                available_clips.append(c)

        # Get the number of rows
        number_of_clips = len(available_clips)
        number_of_rows = int(sqrt(number_of_clips))
        max_clips_on_row = float(number_of_clips) / float(number_of_rows)

        # Determine how many clips per row
        if max_clips_on_row > float(int(max_clips_on_row)):
            max_clips_on_row = int(max_clips_on_row + 1)
        else:
            max_clips_on_row = int(max_clips_on_row)

        # Calculate Height & Width
        height = 1.0 / float(number_of_rows)
        width = 1.0 / float(max_clips_on_row)

        clip_index = 0

        # Loop through each row of clips
        for row in range(0, number_of_rows):

            # Loop through clips on this row
            column_string = " - - - "
            for col in range(0, max_clips_on_row):
                if clip_index < number_of_clips:
                    # Calculate X & Y
                    X = float(col) * width
                    Y = float(row) * height

                    # Modify clip layout settings
                    selected_clip = available_clips[clip_index]
                    selected_clip.data["gravity"] = openshot.GRAVITY_TOP_LEFT

                    if stretch:
                        selected_clip.data["scale"] = openshot.SCALE_STRETCH
                    else:
                        selected_clip.data["scale"] = openshot.SCALE_FIT

                    # Set scale keyframes
                    w = openshot.Point(1, width, openshot.BEZIER)
                    w_object = json.loads(w.Json())
                    selected_clip.data["scale_x"] = { "Points" : [w_object]}
                    h = openshot.Point(1, height, openshot.BEZIER)
                    h_object = json.loads(h.Json())
                    selected_clip.data["scale_y"] = { "Points" : [h_object]}
                    x_point = openshot.Point(1, X, openshot.BEZIER)
                    x_object = json.loads(x_point.Json())
                    selected_clip.data["location_x"] = { "Points" : [x_object]}
                    y_point = openshot.Point(1, Y, openshot.BEZIER)
                    y_object = json.loads(y_point.Json())
                    selected_clip.data["location_y"] = { "Points" : [y_object]}

                    log.info('Updating clip id: %s' % selected_clip.data["id"])
                    log.info('width: %s, height: %s' % (width, height))

                    # Increment Clip Index
                    clip_index += 1

                    # Save changes
                    self.update_clip_data(selected_clip.data, only_basic_props=False, ignore_reader=True)

    def Reverse_Transition_Triggered(self, tran_ids):
        """Callback for reversing a transition"""
        log.info("Reverse_Transition_Triggered")

        # Loop through all selected transitions
        for tran_id in tran_ids:

            # Get existing clip object
            tran = Transition.get(id=tran_id)

            # Loop through brightness keyframes
            tran_data_copy = deepcopy(tran.data)
            new_index = len(tran.data["brightness"]["Points"])
            for point in tran.data["brightness"]["Points"]:
                new_index -= 1
                tran_data_copy["brightness"]["Points"][new_index]["co"]["Y"] = point["co"]["Y"]
                if "handle_left" in point:
                    tran_data_copy["brightness"]["Points"][new_index]["handle_left"]["Y"] = point["handle_left"]["Y"]
                    tran_data_copy["brightness"]["Points"][new_index]["handle_right"]["Y"] = point["handle_right"]["Y"]

            # Save changes
            self.update_transition_data(tran_data_copy, only_basic_props=False)

    @pyqtSlot(str)
    def ShowTransitionMenu(self, tran_id=None):
        log.info('ShowTransitionMenu: %s' % tran_id)

        # Get translation method
        _ = get_app()._tr

        # Set the selected transition (if needed)
        if tran_id not in self.window.selected_transitions:
            self.window.addSelection(tran_id, 'transition')
        # Get list of all selected transitions
        tran_ids = self.window.selected_transitions
        clip_ids = self.window.selected_clips

        # Get framerate
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Get existing transition object
        tran = Transition.get(id=tran_id)
        playhead_position = float(self.window.preview_thread.current_frame) / fps_float

        menu = QMenu(self)

        # Copy Menu
        if len(tran_ids) + len(clip_ids) > 1:
            # Copy All Menu (Clips and/or transitions are selected)
            Copy_All = menu.addAction(_("Copy"))
            Copy_All.setShortcut(QKeySequence(self.window.getShortcutByName("copyAll")))
            Copy_All.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_ALL, clip_ids, tran_ids))
        else:
            # Only a single transitions is selected (show normal transition copy menu)
            Copy_Menu = QMenu(_("Copy"), self)
            Copy_Tran = Copy_Menu.addAction(_("Transition"))
            Copy_Tran.setShortcut(QKeySequence(self.window.getShortcutByName("copyAll")))
            Copy_Tran.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_TRANSITION, [], [tran_id]))

            Keyframe_Menu = QMenu(_("Keyframes"), self)
            Copy_Keyframes_All = Keyframe_Menu.addAction(_("All"))
            Copy_Keyframes_All.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_KEYFRAMES_ALL, [], [tran_id]))
            Keyframe_Menu.addSeparator()
            Copy_Keyframes_Brightness = Keyframe_Menu.addAction(_("Brightness"))
            Copy_Keyframes_Brightness.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_KEYFRAMES_BRIGHTNESS, [], [tran_id]))
            Copy_Keyframes_Scale = Keyframe_Menu.addAction(_("Contrast"))
            Copy_Keyframes_Scale.triggered.connect(partial(self.Copy_Triggered, MENU_COPY_KEYFRAMES_CONTRAST, [], [tran_id]))

            # Only show copy->keyframe if a single transitions is selected
            Copy_Menu.addMenu(Keyframe_Menu)
            menu.addMenu(Copy_Menu)

        # Get list of clipboard items (that are complete clips or transitions)
        # i.e. ignore partial clipboard items (keyframes / effects / etc...)
        clipboard_clip_ids = [k for k, v in self.copy_clipboard.items() if v.get('id')]
        clipboard_tran_ids = [k for k, v in self.copy_transition_clipboard.items() if v.get('id')]
        # Determine if the paste menu should be shown
        if self.copy_transition_clipboard and len(clipboard_clip_ids) + len(clipboard_tran_ids) == 0:
            # Paste Menu (Only show when partial transition clipboard avaialble)
            Paste_Tran = menu.addAction(_("Paste"))
            Paste_Tran.triggered.connect(partial(self.Paste_Triggered, MENU_PASTE, 0.0, 0, [], tran_ids))

        menu.addSeparator()

        # Alignment Menu (if multiple selections)
        if len(clip_ids) > 1:
            Alignment_Menu = QMenu(_("Align"), self)
            Align_Left = Alignment_Menu.addAction(_("Left"))
            Align_Left.triggered.connect(partial(self.Align_Triggered, MENU_ALIGN_LEFT, clip_ids, tran_ids))
            Align_Right = Alignment_Menu.addAction(_("Right"))
            Align_Right.triggered.connect(partial(self.Align_Triggered, MENU_ALIGN_RIGHT, clip_ids, tran_ids))

            # Add menu to parent
            menu.addMenu(Alignment_Menu)

        # If Playhead overlapping transition
        if tran:
            start_of_tran = float(tran.data["start"])
            end_of_tran = float(tran.data["end"])
            position_of_tran = float(tran.data["position"])
            if playhead_position >= position_of_tran and playhead_position <= (position_of_tran + (end_of_tran - start_of_tran)):
                # Add split transition menu
                Slice_Menu = QMenu(_("Slice"), self)
                Slice_Keep_Both = Slice_Menu.addAction(_("Keep Both Sides"))
                Slice_Keep_Both.triggered.connect(partial(self.Slice_Triggered, MENU_SLICE_KEEP_BOTH, [], [tran_id], playhead_position))
                Slice_Keep_Left = Slice_Menu.addAction(_("Keep Left Side"))
                Slice_Keep_Left.triggered.connect(partial(self.Slice_Triggered, MENU_SLICE_KEEP_LEFT, [], [tran_id], playhead_position))
                Slice_Keep_Right = Slice_Menu.addAction(_("Keep Right Side"))
                Slice_Keep_Right.triggered.connect(partial(self.Slice_Triggered, MENU_SLICE_KEEP_RIGHT, [], [tran_id], playhead_position))
                menu.addMenu(Slice_Menu)

        # Reverse Transition menu
        Reverse_Transition = menu.addAction(_("Reverse Transition"))
        Reverse_Transition.triggered.connect(partial(self.Reverse_Transition_Triggered, tran_ids))

        # Properties
        menu.addSeparator()
        menu.addAction(self.window.actionProperties)

        # Remove transition menu
        menu.addSeparator()
        menu.addAction(self.window.actionRemoveTransition)

        # Show menu
        return menu.popup(QCursor.pos())

    @pyqtSlot(str)
    def ShowTrackMenu(self, layer_id=None):
        log.info('ShowTrackMenu: %s' % layer_id)

        if layer_id not in self.window.selected_tracks:
            self.window.selected_tracks = [layer_id]

        # Get track object
        track = Track.get(id=layer_id)

        menu = QMenu(self)
        menu.addAction(self.window.actionAddTrackAbove)
        menu.addAction(self.window.actionAddTrackBelow)
        menu.addAction(self.window.actionRenameTrack)
        if track.data['lock']:
            menu.addAction(self.window.actionUnlockTrack)
        else:
            menu.addAction(self.window.actionLockTrack)
        menu.addSeparator()
        menu.addAction(self.window.actionRemoveTrack)
        return menu.popup(QCursor.pos())

    @pyqtSlot(str)
    def ShowMarkerMenu(self, marker_id=None):
        log.info('ShowMarkerMenu: %s' % marker_id)

        if marker_id not in self.window.selected_markers:
            self.window.selected_markers = [marker_id]

        menu = QMenu(self)
        menu.addAction(self.window.actionRemoveMarker)
        return menu.popup(QCursor.pos())

    @pyqtSlot(str, int)
    def PreviewClipFrame(self, clip_id, frame_number):

        # Get existing clip object
        clip = Clip.get(id=clip_id)
        path = clip.data['reader']['path']

        # Adjust frame # to valid range
        frame_number = max(frame_number, 1)
        frame_number = min(frame_number, int(clip.data['reader']['video_length']))

        # Load the clip into the Player (ignored if this has already happened)
        self.window.LoadFileSignal.emit(path)
        self.window.SpeedSignal.emit(0)

        # Seek to frame
        self.window.SeekSignal.emit(frame_number)

    @pyqtSlot(float, int, str)
    def PlayheadMoved(self, position_seconds, position_frames, time_code):

        # Load the timeline into the Player (ignored if this has already happened)
        self.window.LoadFileSignal.emit('')

        if self.last_position_frames != position_frames:
            # Update time code (to prevent duplicate previews)
            self.last_position_frames = position_frames

            # Notify main window of current frame
            self.window.previewFrame(position_seconds, position_frames, time_code)

    @pyqtSlot(int)
    def movePlayhead(self, position_frames):
        """ Move the playhead since the position has changed inside OpenShot (probably due to the video player) """

        # Get access to timeline scope and set scale to zoom slider value (passed in)
        code = JS_SCOPE_SELECTOR + ".MovePlayheadToFrame(" + str(position_frames) + ");"
        self.eval_js(code)

    @pyqtSlot(int)
    def SetSnappingMode(self, enable_snapping):
        """ Enable / Disable snapping mode """

        # Init snapping state (1 = snapping, 0 = no snapping)
        self.eval_js(JS_SCOPE_SELECTOR + ".SetSnappingMode(%s);" % int(enable_snapping))

    @pyqtSlot(int)
    def SetRazorMode(self, enable_razor):
        """ Enable / Disable razor mode """

        # Init razor state (1 = razor, 0 = no razor)
        self.eval_js(JS_SCOPE_SELECTOR + ".SetRazorMode(%s);" % int(enable_razor))

    @pyqtSlot(str, str, bool)
    def addSelection(self, item_id, item_type, clear_existing=False):
        """ Add the selected item to the current selection """

        # Add to main window
        self.window.addSelection(item_id, item_type, clear_existing)

    @pyqtSlot(str, str)
    def removeSelection(self, item_id, item_type):
        """ Remove the selected clip from the selection """

        # Remove from main window
        self.window.removeSelection(item_id, item_type)

    @pyqtSlot(str)
    def qt_log(self, message=None):
        log.info(message)

    # Handle changes to zoom level, update js
    def update_zoom(self, newValue):
        _ = get_app()._tr

        # Set zoom label
        self.window.zoomScaleLabel.setText(_("{} seconds").format(newValue))

        # Determine X coordinate of cursor (to center zoom on)
        cursor_y = self.mapFromGlobal(self.cursor().pos()).y()
        if cursor_y >= 0:
            cursor_x = self.mapFromGlobal(self.cursor().pos()).x()
        else:
            cursor_x = 0

        # Get access to timeline scope and set scale to zoom slider value (passed in)
        cmd = JS_SCOPE_SELECTOR + ".setScale(" + str(newValue) + "," + str(cursor_x) + ");"
        self.page().mainFrame().evaluateJavaScript(cmd)

        # Start timer to redraw audio
        self.redraw_audio_timer.start()

        # Save current zoom
        get_app().updates.update(["scale"], newValue)

    def keyPressEvent(self, event):
        """ Keypress callback for timeline """
        key_value = event.key()
        if (key_value == Qt.Key_Shift or key_value == Qt.Key_Control):

            # Only pass a few keystrokes to the webview (CTRL and SHIFT)
            return QWebView.keyPressEvent(self, event)

        else:
            # Ignore most keypresses
            event.ignore()

    # Capture wheel event to alter zoom slider control
    def wheelEvent(self, event):
        if int(QCoreApplication.instance().keyboardModifiers() & Qt.ControlModifier) > 0:
            # For each 120 (standard scroll unit) adjust the zoom slider
            tick_scale = 120
            steps = int(event.angleDelta().y() / tick_scale)
            self.window.sliderZoom.setValue(self.window.sliderZoom.value() - self.window.sliderZoom.pageStep() * steps)
        else:
            # Otherwise pass on to implement default functionality (scroll in QWebView)
            super(type(self), self).wheelEvent(event)

    def setup_js_data(self):
        # Export self as a javascript object in webview
        self.page().mainFrame().addToJavaScriptWindowObject('timeline', self)
        self.page().mainFrame().addToJavaScriptWindowObject('mainWindow', self.window)

        # Initialize snapping mode
        self.SetSnappingMode(self.window.actionSnappingTool.isChecked())

    # An item is being dragged onto the timeline (mouse is entering the timeline now)
    def dragEnterEvent(self, event):

        # If a plain text drag accept
        if not self.new_item and not event.mimeData().hasUrls() and event.mimeData().html():
            # get type of dropped data
            self.item_type = event.mimeData().html()

            # Track that a new item is being 'added'
            self.new_item = True

            # Get the mime data (i.e. list of files, list of transitions, etc...)
            data = json.loads(event.mimeData().text())
            pos = event.posF()

            # create the item
            if self.item_type == "clip":
                self.addClip(data, pos)
            elif self.item_type == "transition":
                self.addTransition(data, pos)

            # accept all events, even if a new clip is not being added
            event.accept()

        # Accept a plain file URL (from the OS)
        elif not self.new_item and event.mimeData().hasUrls():
            # Track that a new item is being 'added'
            self.new_item = True
            self.item_type = "os_drop"

            # accept event
            event.accept()

    # Add Clip
    def addClip(self, data, position):

        # Get app object
        app = get_app()

        # Search for matching file in project data (if any)
        file_id = data[0]
        file = File.get(id=file_id)

        if (file.data["media_type"] == "video" or file.data["media_type"] == "image"):
            # Determine thumb path
            thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file.data["id"])
        else:
            # Audio file
            thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")

        # Get file name
        path, filename = os.path.split(file.data["path"])

        # Convert path to the correct relative path (based on this folder)
        file_path = file.absolute_path()

        # Create clip object for this file
        c = openshot.Clip(file_path)

        # Append missing attributes to Clip JSON
        new_clip = json.loads(c.Json())
        new_clip["file_id"] = file.id
        new_clip["title"] = filename
        new_clip["image"] = thumb_path

        # Skip any clips that are missing a 'reader' attribute
        # TODO: Determine why this even happens, as it shouldn't be possible
        if not new_clip.get("reader"):
            return  # Do nothing

        # Check for optional start and end attributes
        start_frame = 1
        end_frame = new_clip["reader"]["duration"]
        if 'start' in file.data.keys():
            new_clip["start"] = file.data['start']
        if 'end' in file.data.keys():
            new_clip["end"] = file.data['end']

        # Find the closest track (from javascript)
        top_layer = int(self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptTrack(" + str(position.y()) + ");"))
        new_clip["layer"] = top_layer

        # Find position from javascript
        js_position = self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptPosition(" + str(position.x()) + ");")
        new_clip["position"] = js_position

        # Adjust clip duration, start, and end
        new_clip["duration"] = new_clip["reader"]["duration"]
        if file.data["media_type"] == "image":
            new_clip["end"] = self.settings.get("default-image-length")  # default to 8 seconds

        # Overwrite frame rate (incase the user changed it in the File Properties)
        file_properties_fps = float(file.data["fps"]["num"]) / float(file.data["fps"]["den"])
        file_fps = float(new_clip["reader"]["fps"]["num"]) / float(new_clip["reader"]["fps"]["den"])
        fps_diff = file_fps / file_properties_fps
        new_clip["reader"]["fps"]["num"] = file.data["fps"]["num"]
        new_clip["reader"]["fps"]["den"] = file.data["fps"]["den"]
        # Scale duration / length / and end properties
        new_clip["reader"]["duration"] *= fps_diff
        new_clip["end"] *= fps_diff
        new_clip["duration"] *= fps_diff

        # Add clip to timeline
        self.update_clip_data(new_clip, only_basic_props=False)

        # temp hold item_id
        self.item_id = new_clip.get('id')

        # Init javascript bounding box (for snapping support)
        code = JS_SCOPE_SELECTOR + ".StartManualMove('" + self.item_type + "', '" + self.item_id + "');"
        self.eval_js(code)

    # Resize timeline
    @pyqtSlot(float)
    def resizeTimeline(self, new_duration):
        """Resize the duration of the timeline"""
        get_app().updates.update(["duration"], new_duration)

    # Add Transition
    def addTransition(self, file_ids, position):
        log.info("addTransition...")

        # Find the closest track (from javascript)
        top_layer = int(self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptTrack(" + str(position.y()) + ");"))

        # Find position from javascript
        js_position = self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptPosition(" + str(position.x()) + ");")

        # Get FPS from project
        fps = get_app().project.get(["fps"])
        fps_float = float(fps["num"]) / float(fps["den"])

        # Open up QtImageReader for transition Image
        transition_reader = openshot.QtImageReader(file_ids[0])

        brightness = openshot.Keyframe()
        brightness.AddPoint(1, 1.0, openshot.BEZIER)
        brightness.AddPoint(round(10 * fps_float) + 1, -1.0, openshot.BEZIER)
        contrast = openshot.Keyframe(3.0)

        # Create transition dictionary
        transitions_data = {
            "id": get_app().project.generate_id(),
            "layer": top_layer,
            "title": "Transition",
            "type": "Mask",
            "position": js_position,
            "start": 0,
            "end": 10,
            "brightness": json.loads(brightness.Json()),
            "contrast": json.loads(contrast.Json()),
            "reader": json.loads(transition_reader.Json()),
            "replace_image": False
        }

        # Send to update manager
        self.update_transition_data(transitions_data, only_basic_props=False)

        # temp keep track of id
        self.item_id = transitions_data.get('id')

        # Init javascript bounding box (for snapping support)
        code = JS_SCOPE_SELECTOR + ".StartManualMove('" + self.item_type + "', '" + self.item_id + "');"
        self.eval_js(code)

    # Add Effect
    def addEffect(self, effect_names, position):
        log.info("addEffect: %s at %s" % (effect_names, position))
        # Get name of effect
        name = effect_names[0]

        # Find the closest track (from javascript)
        closest_layer = int(self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptTrack(" + str(position.y()) + ");"))

        # Find position from javascript
        js_position = self.eval_js(JS_SCOPE_SELECTOR + ".GetJavaScriptPosition(" + str(position.x()) + ");")

        # Loop through clips on the closest layer
        possible_clips = Clip.filter(layer=closest_layer)
        for clip in possible_clips:
            if js_position == 0 or (clip.data["position"] <= js_position <= clip.data["position"] + (
                        clip.data["end"] - clip.data["start"])):
                log.info("Applying effect to clip")
                log.info(clip)

                # Create Effect
                effect = openshot.EffectInfo().CreateEffect(name)

                # Get Effect JSON
                effect.Id(get_app().project.generate_id())
                effect_json = json.loads(effect.Json())

                # Append effect JSON to clip
                clip.data["effects"].append(effect_json)

                # Update clip data for project
                self.update_clip_data(clip.data, only_basic_props=False, ignore_reader=True)

    # Without defining this method, the 'copy' action doesn't show with cursor
    def dragMoveEvent(self, event):
        # Accept all move events
        event.accept()

        # Get cursor position
        pos = event.posF()

        # Move clip on timeline
        if self.item_type in ["clip", "transition"]:
            code = JS_SCOPE_SELECTOR + ".MoveItem(" + str(pos.x()) + ", " + str(pos.y()) + ", '" + self.item_type + "');"
            self.eval_js(code)

    # Drop an item on the timeline
    def dropEvent(self, event):
        log.info("Dropping item on timeline - item_id: %s, item_type: %s" % (self.item_id, self.item_type))

        # Get position of cursor
        pos = event.posF()

        if self.item_type in ["clip", "transition"]:
            # Update most recent clip
            self.eval_js(JS_SCOPE_SELECTOR + ".UpdateRecentItemJSON('" + self.item_type + "', '" + self.item_id + "');")

        elif self.item_type == "effect":
            # Add effect only on drop
            data = json.loads(event.mimeData().text())
            self.addEffect(data, pos)

        elif self.item_type == "os_drop":
            # Add new files to project
            get_app().window.filesTreeView.dropEvent(event)

            # Add clips for each file dropped
            for uri in event.mimeData().urls():
                file_url = urlparse(uri.toString())
                if file_url.scheme == "file":
                    filepath = file_url.path
                    if filepath[0] == "/" and ":" in filepath:
                        filepath = filepath[1:]
                    if os.path.exists(filepath.encode('UTF-8')) and os.path.isfile(filepath.encode('UTF-8')):
                        # Valid file, so create clip for it
                        for file in File.filter(path=filepath):
                            # Insert clip for this file at this position
                            self.addClip([file.id], pos)

        # Clear new clip
        self.new_item = False
        self.item_type = None
        self.item_id = None

        # Accept event
        event.accept()

        # Update the preview and reselct current frame in properties
        get_app().window.refreshFrameSignal.emit()
        get_app().window.propertyTableView.select_frame(self.window.preview_thread.player.Position())

    def dragLeaveEvent(self, event):
        """A drag is in-progress and the user moves mouse outside of timeline"""
        log.info('dragLeaveEvent - Undo drop')
        if self.item_type == "clip":
            get_app().window.actionRemoveClip.trigger()
        elif self.item_type == "transition":
            get_app().window.actionRemoveTransition.trigger()

        # Clear new clip
        self.new_item = False
        self.item_type = None
        self.item_id = None

        # Accept event
        event.accept()

    def redraw_audio_onTimeout(self):
        """Timer is ready to redraw audio (if any)"""
        log.info('redraw_audio_onTimeout')

        # Stop timer
        self.redraw_audio_timer.stop()

        # Pass to javascript timeline (and render)
        cmd = JS_SCOPE_SELECTOR + ".reDrawAllAudioData();"
        self.page().mainFrame().evaluateJavaScript(cmd)

    def ClearAllSelections(self):
        """Clear all selections in JavaScript"""

        # Call javascript command
        cmd = JS_SCOPE_SELECTOR + ".ClearAllSelections();"
        self.page().mainFrame().evaluateJavaScript(cmd)

    def SelectAll(self):
        """Select all clips and transitions in JavaScript"""

        # Call javascript command
        cmd = JS_SCOPE_SELECTOR + ".SelectAll();"
        self.page().mainFrame().evaluateJavaScript(cmd)

    def render_cache_json(self):
        """Render the cached frames to the timeline (called every X seconds), and only if changed"""

        # Get final cache object from timeline
        try:
            cache_object = get_app().window.timeline_sync.timeline.GetCache()
            if cache_object and cache_object.Count() > 0:
                # Get the JSON from the cache object (i.e. which frames are cached)
                cache_json = get_app().window.timeline_sync.timeline.GetCache().Json()
                cache_dict = json.loads(cache_json)
                cache_version = cache_dict["version"]

                if self.cache_renderer_version != cache_version:
                    # Cache has changed, re-render it
                    self.cache_renderer_version = cache_version

                    cmd = JS_SCOPE_SELECTOR + ".RenderCache(" + cache_json + ");"
                    self.page().mainFrame().evaluateJavaScript(cmd)
        finally:
            # ignore any errors inside the cache rendering
            pass

    def __init__(self, window):
        QWebView.__init__(self)
        self.window = window
        self.setAcceptDrops(True)
        self.last_position_frames = None

        # Get settings
        self.settings = settings.get_settings()

        # Add self as listener to project data updates (used to update the timeline)
        get_app().updates.add_listener(self)

        # set url from configuration (QUrl takes absolute paths for file system paths, create from QFileInfo)
        self.setUrl(QUrl.fromLocalFile(QFileInfo(self.html_path).absoluteFilePath()))

        # Connect signal of javascript initialization to our javascript reference init function
        self.page().mainFrame().javaScriptWindowObjectCleared.connect(self.setup_js_data)

        # Connect zoom functionality
        window.sliderZoom.valueChanged.connect(self.update_zoom)

        # Connect waveform generation signal
        get_app().window.WaveformReady.connect(self.Waveform_Ready)

        # Copy clipboard
        self.copy_clipboard = {}
        self.copy_transition_clipboard = {}

        # Init New clip
        self.new_item = False
        self.item_type = None
        self.item_id = None

        # Delayed zoom audio redraw
        self.redraw_audio_timer = QTimer(self)
        self.redraw_audio_timer.setInterval(300)
        self.redraw_audio_timer.timeout.connect(self.redraw_audio_onTimeout)

        # QTimer for cache rendering
        self.cache_renderer_version = None
        self.cache_renderer = QTimer(self)
        self.cache_renderer.setInterval(0.5 * 1000)
        self.cache_renderer.timeout.connect(self.render_cache_json)

        # Delay the start of cache rendering
        QTimer.singleShot(1500, self.cache_renderer.start)