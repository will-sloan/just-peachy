"""Small rigid-body/quaternion operations; conventions and commands: README_IMU.md."""
import math


GRAVITY = 9.80665
IDENTITY = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))


def dot(a, b): return sum(x*y for x, y in zip(a, b))
def norm(v): return math.sqrt(dot(v, v))
def add(a, b): return tuple(x+y for x, y in zip(a, b))
def scale(v, s): return tuple(x*s for x in v)
def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def unit(v):
    n = norm(v)
    if n < 1e-9: raise ValueError('Direction has zero length')
    return scale(v, 1/n)


def vector(value, name):
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(type(x) not in (float, int) or not math.isfinite(x) for x in value)):
        raise ValueError(name+' must contain three finite numbers')
    return tuple(float(x) for x in value)


def matvec(matrix, v): return tuple(dot(row, v) for row in matrix)
def conjugate(q): return (q[0], -q[1], -q[2], -q[3])


def multiply(p, q):
    return (p[0]*q[0]-dot(p[1:], q[1:]),
            *add(add(scale(q[1:], p[0]), scale(p[1:], q[0])), cross(p[1:], q[1:])))


def rotation_vector(v):
    """Radians about body axes -> Hamilton unit quaternion, scalar first."""
    angle = norm(v)
    if angle < 1e-12: return (1., 0., 0., 0.)
    return (math.cos(angle/2), *scale(v, math.sin(angle/2)/angle))


def rotate(q, v):
    t = scale(cross(q[1:], v), 2.)
    return add(v, add(scale(t, q[0]), cross(q[1:], t)))


def integrate(q, omega, dt):
    result = multiply(q, rotation_vector(scale(omega, dt)))
    return scale(result, 1/norm(result))


def specific_force_at_array(acc_sensor_g, omega, alpha, sensor_from_array_m):
    """All vectors in device coordinates; omega rad/s, alpha rad/s^2.

    r points FROM sensor TO array. Specific force has the same rigid lever-arm
    correction as acceleration because gravity cancels between the two points.
    This does not estimate the array's translation or position.
    """
    r = scale(sensor_from_array_m, -1.)
    correction = add(cross(alpha, r), cross(omega, cross(omega, r)))
    return add(acc_sensor_g, scale(correction, 1/GRAVITY))


class MountGeometry:
    """One installation's geometry, never inferred from cable colours/direction.

    Device axes: X screen-right, Y screen-top, Z out of the screen, viewed from
    its front in portrait. sensor_to_device is a proper rotation of raw Bosch
    axes. array_zero_axis_device points along the array towards XVF native 0
    degrees (MIC3 end on the standard linear board), not a screen assumption.
    """
    def __init__(self, config=None):
        cfg = {} if config is None else config
        if not isinstance(cfg, dict): raise ValueError('mount must be an object')
        for key in ('axes_verified', 'offset_verified'):
            if type(cfg.get(key, False)) is not bool: raise ValueError(key+' must be boolean')
        matrix = cfg.get('sensor_to_device', IDENTITY)
        if not isinstance(matrix, (tuple, list)) or len(matrix) != 3:
            raise ValueError('sensor_to_device must be a 3 by 3 rotation')
        self.rotation = tuple(vector(row, 'sensor_to_device row') for row in matrix)
        if (any(abs(dot(a, b)-(1. if i == j else 0.)) > 1e-6
                for i, a in enumerate(self.rotation) for j, b in enumerate(self.rotation))
                or abs(dot(self.rotation[0], cross(self.rotation[1], self.rotation[2]))-1.) > 1e-6):
            raise ValueError('sensor_to_device must be orthonormal and right-handed (determinant +1)')
        axis = vector(cfg.get('array_zero_axis_device', (1., 0., 0.)), 'array_zero_axis_device')
        if abs(norm(axis)-1.) > 1e-6: raise ValueError('array_zero_axis_device must be a unit vector')
        self.array_axis = axis
        self.verified = cfg.get('axes_verified', False)
        if self.verified and not all(k in cfg for k in ('sensor_to_device', 'array_zero_axis_device')):
            raise ValueError('Verified axes require both explicit sensor and array alignment')
        self.offset = vector(cfg.get('sensor_position_from_array_m', (0., 0., 0.)), 'sensor_position_from_array_m')
        if norm(self.offset) > 1.: raise ValueError('Sensor offset exceeds the prototype geometry (1 metre)')
        self.offset_verified = cfg.get('offset_verified', False)
        if self.offset_verified and 'sensor_position_from_array_m' not in cfg:
            raise ValueError('Verified offset requires explicit sensor_position_from_array_m')

    def map(self, v): return matvec(self.rotation, v)


def horizontal_candidates(native_angle_deg, axis_xy):
    """Solve a_horizontal dot direction = cos(native_angle).

    Assumes the talker direction is horizontal. The linear array supplies a
    cone (one projection), not full 3D azimuth. A tilted baseline changes the
    cone/horizontal-plane intersection, so simply adding yaw is insufficient.
    Returns both possible azimuths in [-180, 180); caller owns ambiguity policy.
    """
    if (type(native_angle_deg) not in (int, float) or not math.isfinite(native_angle_deg)
            or not 0. <= native_angle_deg <= 180.):
        return ()
    projection = math.hypot(*axis_xy)
    if projection < .25: return ()  # Near-vertical baseline: horizontal direction is ill-conditioned.
    cosine = math.cos(math.radians(native_angle_deg))/projection
    if abs(cosine) > 1.+1e-9: return ()  # Incompatible with the horizontal-source assumption.
    offset = math.degrees(math.acos(max(-1., min(1., cosine))))
    heading = math.degrees(math.atan2(axis_xy[1], axis_xy[0]))
    return tuple((heading+s*offset+180.) % 360.-180. for s in (1., -1.))
