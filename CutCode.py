from LaserCommandConstants import *
from RasterPlotter import RasterPlotter, X_AXIS, TOP, BOTTOM, Y_AXIS, RIGHT, LEFT, UNIDIRECTIONAL
from svgelements import *
from zinglplotter import ZinglPlotter

"""
Cutcode is a list of cut objects. These are line, quad, cubic, arc, and raster. And anything else that should be
considered a laser primitive. These are disjointed objects. If the distance between one and the next exist the laser 
should be toggled and move by anything executing these in the planning process. Various other laser-file types should
be converted into cut code. This should be the parsed form of file-blobs. Cutcode can convert easily to both SVG and
to LaserCode.

All CutObjects have a .start() .end() and .generator() functions. They also have a settings object that contains all 
properties for that cuts may need or use. Or which may be used by the CutPlanner, PlotPlanner, or local objects. These
are references to settings which may be shared by all CutObjects created by a LaserOperation.  
"""


class LaserSettings:
    def __init__(self, *args, **kwargs):
        self.laser_enabled = True
        self.speed = 20.0
        self.power = 1000.0
        self.dratio_custom = False
        self.dratio = 0.261
        self.acceleration_custom = False
        self.acceleration = 1

        self.raster_step = 0
        self.raster_direction = 0
        self.raster_swing = False  # False = bidirectional, True = Unidirectional
        self.raster_preference_top = 0
        self.raster_preference_right = 0
        self.raster_preference_left = 0
        self.raster_preference_bottom = 0
        self.overscan = 20

        self.advanced = False

        self.ppi_enabled = True

        self.dot_length_custom = False
        self.dot_length = 1

        self.shift_enabled = False

        self.passes_custom = False
        self.passes = 1

        self.jog_distance = 255
        self.jog_enable = True

        for k in kwargs:
            value = kwargs[k]
            if hasattr(self, k):
                t = type(getattr(self, k))
                setattr(self, k, t(value))
        if len(args) == 1:
            obj = args[0]
            try:
                obj = obj.settings
            except AttributeError:
                pass
            if isinstance(obj, LaserSettings):
                self.set_values(obj)

    def set_values(self, obj):
        for q in dir(obj):
            if q.startswith('_') or q.startswith('implicit'):
                continue
            value = getattr(obj, q)
            if isinstance(value, (int, float, bool, str)):
                setattr(self, q, value)

    @property
    def implicit_accel(self):
        if not self.acceleration_custom:
            return None
        return self.acceleration

    @property
    def implicit_d_ratio(self):
        if not self.dratio_custom:
            return None
        return self.dratio

    @property
    def implicit_dotlength(self):
        if not self.dot_length_custom:
            return 1
        return self.dot_length

    @property
    def implicit_passes(self):
        if not self.passes_custom:
            return 1
        return self.passes


class CutCode(list):
    def __init__(self):
        list.__init__(self)

    def __str__(self):
        parts = list()
        parts.append("%d items" % len(self))
        return 'CutCode(%s)' % ' '.join(parts)

    def as_svg(self):
        svg = []
        for e in self:
            svg.append(e.as_svg())
        return svg

    def cross(self, j, k):
        """
        Reverses subpaths flipping the individual elements from position j inclusive to
        k exclusive.

        :param subpaths:
        :param j:
        :param k:
        :return:
        """
        for q in range(j, k):
            self[q].direct_close()
            self[q].reverse()
        self[j:k] = self[j:k][::-1]

    def generate(self):
        for cutobject in self:
            yield COMMAND_PLOT, cutobject
        yield COMMAND_PLOT_START


class CutObject:
    def __init__(self, start=None, end=None, settings=None):
        if settings is None:
            settings = LaserSettings()
        self.settings = settings
        self._start = start
        self._end = end

    def start(self):
        return self._start

    def end(self):
        return self._end

    def major_axis(self):
        start = self.start()
        end = self.end()
        if (start.x - end.x) - (start.y - end.y) < 0:
            return 1
        else:
            return 0

    def x_dir(self):
        start = self.start()
        end = self.end()
        if start.x < end.x:
            return 1
        else:
            return 0

    def y_dir(self):
        start = self.start()
        end = self.end()
        if start.y < end.y:
            return 1
        else:
            return 0

    def reverse(self):
        self._start, self._end = self._end, self._start

    def generator(self):
        raise NotImplemented


class LineCut(CutObject):
    def __init__(self, start_point, end_point, settings=None):
        CutObject.__init__(self, start_point, end_point, settings=settings)

    def generator(self):
        return ZinglPlotter.plot_line(self._start[0], self._start[1], self._end[0], self._end[1])


class QuadCut(CutObject):
    def __init__(self, start_point, control_point, end_point, settings=None):
        CutObject.__init__(self, start_point, end_point, settings=settings)
        self.control = control_point

    def generator(self):
        return ZinglPlotter.plot_quad_bezier(self._start[0], self._start[1],
                                             self.control[0], self.control[1],
                                             self._end[0], self._end[1])


class CubicCut(CutObject):
    def __init__(self, start_point, control1, control2, end_point, settings=None):
        CutObject.__init__(self, start_point, end_point, settings=settings)
        self.control1 = control1
        self.control2 = control2

    def reverse(self):
        self.control1, self.control2 = self.control2, self.control1
        CutObject.reverse(self)

    def generator(self):
        return ZinglPlotter.plot_cubic_bezier(self._start[0], self._start[1],
                                              self.control1[0], self.control1[1],
                                              self.control2[0], self.control2[1],
                                              self._end[0], self._end[1])


class ArcCut(CutObject):
    def __init__(self, arc, settings=None):
        CutObject.__init__(self, settings=settings)
        self.arc = arc

    def start(self):
        return self.arc.start

    def end(self):
        return self.arc.end

    def reverse(self):
        self.arc = copy(self.arc).reversed()

    def generator(self):
        return ZinglPlotter.plot_arc(self.arc)


class RasterCut(CutObject):
    def __init__(self, image, settings=None):
        CutObject.__init__(self, settings=settings)
        self.image = image
        step = self.settings.raster_step
        if step <= 0:
            step = 1
        direction = self.settings.raster_direction
        traverse = 0
        if direction == 0:
            traverse |= X_AXIS
            traverse |= TOP
        elif direction == 1:
            traverse |= X_AXIS
            traverse |= BOTTOM
        elif direction == 2:
            traverse |= Y_AXIS
            traverse |= RIGHT
        elif direction == 3:
            traverse |= Y_AXIS
            traverse |= LEFT
        elif direction == 4:
            traverse |= X_AXIS
            traverse |= TOP
        if self.settings.raster_swing:
            traverse |= UNIDIRECTIONAL

        svgimage = self.image
        image = svgimage.image
        width, height = image.size
        mode = image.mode

        if mode != "1" and mode != "P" and mode != "L" and mode != "RGB" and mode != "RGBA":
            # Any mode without a filter should get converted.
            image = image.convert("RGBA")
            mode = image.mode
        if mode == "1":
            def image_filter(pixel):
                return (255 - pixel) / 255.0
        elif mode == "P":
            p = image.getpalette()

            def image_filter(pixel):
                v = p[pixel * 3] + p[pixel * 3 + 1] + p[pixel * 3 + 2]
                return 1.0 - v / 765.0
        elif mode == "L":
            def image_filter(pixel):
                return (255 - pixel) / 255.0
        elif mode == "RGB":
            def image_filter(pixel):
                return 1.0 - (pixel[0] + pixel[1] + pixel[2]) / 765.0
        elif mode == "RGBA":
            def image_filter(pixel):
                return (1.0 - (pixel[0] + pixel[1] + pixel[2]) / 765.0) * pixel[3] / 255.0
        else:
            raise ValueError  # this shouldn't happen.
        m = svgimage.transform
        data = image.load()

        overscan = self.settings.overscan
        if overscan is None:
            overscan = 20
        else:
            try:
                overscan = int(overscan)
            except ValueError:
                overscan = 20
        tx = m.value_trans_x()
        ty = m.value_trans_y()
        self.plot = RasterPlotter(data, width, height, traverse, 0, overscan,
                             tx,
                             ty,
                             step, image_filter)

    def start(self):
        return Point(self.plot.initial_position_in_scene())

    def end(self):
        return Point(self.plot.final_position_in_scene())

    def major_axis(self):
        right, bottom, x_axis, y_axis = self.plot.initial_direction()
        return 0 if x_axis else 1

    def x_dir(self):
        right, bottom, x_axis, y_axis = self.plot.initial_direction()
        return 1 if right else 0

    def y_dir(self):
        right, bottom, x_axis, y_axis = self.plot.initial_direction()
        return 1 if bottom else 0

    def generator(self):
        return self.plot.plot()