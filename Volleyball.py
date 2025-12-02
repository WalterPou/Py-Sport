from ursina import *
import random

app = Ursina()
player_score = 0
ai_score = 0

# Court boundaries
COURT_X_MIN = -15
COURT_X_MAX = 15
opp_spike = False

last_hitter = None  # "player" or "ai"

score_text = Text("0    -    0", origin=(0,0), y=.45, scale=2)

# --------------------------------------------------
# VISUAL EFFECTS
# --------------------------------------------------

def bump_effect(position, color=color.white):
    """Small bump explosion."""
    e = Entity(
        model='sphere',
        position=position,
        scale=.2,
        color=color,
        emissive=True
    )
    e.animate_scale(1, duration=0.15)
    destroy(e, delay=0.25)

def spike_effect(position):
    """Big shockwave for strong attacks."""
    wave = Entity(
        model='circle',
        position=position,
        scale=0.5,
        rotation_x=90,
        color=color.red,
        emissive=True
    )
    wave.animate_scale(4, duration=0.25, curve=curve.out_expo)
    wave.animate_color(color.clear, duration=0.25)
    destroy(wave, delay=0.3)

    # Bright flash on ball
    flash = Entity(
        model='sphere',
        position=position,
        scale=0.5,
        color=color.rgb(255,80,80),
        emissive=True
    )
    flash.animate_color(color.clear, duration=0.15)
    destroy(flash, delay=0.2)


def camera_shake(intensity=.4, duration=0.2):
    """Quick punch shake."""
    original_pos = camera.position

    def do_shake():
        camera.position = original_pos + Vec3(
            random.uniform(-intensity,intensity),
            random.uniform(-intensity,intensity),
            0
        )

    invoke(do_shake, delay=0)
    invoke(lambda: setattr(camera, "position", original_pos), delay=duration)


# -------------------------------------------
# ENVIRONMENT
# -------------------------------------------

ground = Entity(model='cube', texture='white_cube', scale=(30,1,20), collider='box', color=color.light_gray)
groundLayer = Entity(model='cube', texture='brick', scale=(30,1.1,20), color=color.rgb(0,0,10))
out = Entity(model='cube', texture='grass', scale=(80,1,80), collider='box', color=color.rgb(50,100,50))
net = Entity(model='cube', color=color.rgb(255,255,255), scale=(0.2,3,20), position=(0,2,0), collider='box')

# -------------------------------------------
# BALL
# -------------------------------------------

ball = Entity(
    model='sphere',
    color=color.orange,
    scale=1,
    position=(0,10,0),
    collider='sphere'
)
ball.velocity = Vec3(0,0,0)
GRAVITY = 0.2

# -------------------------------------------
# BALL TRAJECTORY VISUALIZATION
# -------------------------------------------

trajectory_points = []
TRAJECTORY_LENGTH = 20
TRAJECTORY_STEP = 0.08

# Create visual trajectory markers
for i in range(TRAJECTORY_LENGTH):
    p = Entity(model='sphere', scale=.15, color=color.yellow, enabled=False)
    trajectory_points.append(p)


def predict_trajectory():
    """Simulate ball path forward without modifying real ball."""
    points = []

    sim_pos = Vec3(ball.position)
    sim_vel = Vec3(ball.velocity)

    for i in range(TRAJECTORY_LENGTH):

        # Apply gravity
        sim_vel.y -= GRAVITY * TRAJECTORY_STEP

        # Move
        sim_pos += sim_vel * TRAJECTORY_STEP

        # Ground bounce
        if sim_pos.y < 0.1:
            sim_pos.y = 0.5
            sim_vel.y *= -0.6

        # Net collision
        if abs(sim_pos.x - net.x) < 0.3 and sim_pos.y <= net.y + net.scale_y/2:
            sim_vel.x *= -0.5

        points.append(Vec3(sim_pos))

    return points

def play_bump_animation(player):
    # forward bump push
    player.arm_left.animate_position((-0.25, -0.45, 0.4), duration=0.08, curve=curve.linear)
    player.arm_right.animate_position((0.25, -0.45, 0.4), duration=0.08, curve=curve.linear)

    # slight dip
    invoke(
        lambda: [
            player.arm_left.animate_position((-0.25, -0.55, 0.6), duration=0.1, curve=curve.linear),
            player.arm_right.animate_position((0.25, -0.55, 0.6), duration=0.1, curve=curve.linear)
        ],
        delay=0.08
    )

    # return to idle
    invoke(
        lambda: [
            player.arm_left.animate_position((-0.25, -0.4, 0.7), duration=0.12, curve=curve.out_expo),
            player.arm_right.animate_position((0.25, -0.4, 0.7), duration=0.12, curve=curve.out_expo)
        ],
        delay=0.18
    )


# -------------------------------------------
# PLAYER
# -------------------------------------------

class Player(Entity):
    def __init__(self, position=(-10,1,0)):
        super().__init__(visible=False)

        self.position = Vec3(*position)
        self.speed = 10
        self.jump_force = 0.35
        self.vy = 0
        self.on_ground = True
        self.mouse_sensitivity = 80

        # First-person camera
        self.camera = Entity(parent=self, position=(0,1.7,0))
        camera.parent = self.camera
        camera.fov = 95
        camera.position = (0,0,0)
        camera.rotation = (0,0,0)

        mouse.locked = True

        # Hit zone in front of camera
        self.hit_zone = Entity(
            parent=camera,
            model='cube',
            scale=(0.5,0.5,2),
            position=(0,0,1.5),
            color=color.rgba(255,255,255,40),
            collider='box'
        )
        
        # -----------------------------------------
#  First-Person Volleyball Arms
# -----------------------------------------

        # in Player.__init__ after camera setup
        # First-person arms
        self.arm_left = Entity(
            parent=camera,
            model='cube',
            color=color.azure,
            position=Vec3(-0.3, -0.3, 1.5),
            scale=Vec3(0.3, 0.3, 1.5),
            render_queue=100
        )
        self.arm_right = Entity(
            parent=camera,
            model='cube',
            color=color.azure,
            position=Vec3(0.3, -0.3, 1.5),
            scale=Vec3(0.3, 0.3, 1.5),
            render_queue=100
        )


    def update(self):
        global serve_mode

        if serve_mode:
            return

        # ----- MOUSE LOOK -----
        camera.rotation_x -= mouse.velocity[1] * self.mouse_sensitivity
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity
        camera.rotation_x = clamp(camera.rotation_x, -80, 80)

        # ----- MOVEMENT -----
        forward = self.forward * (held_keys['w'] - held_keys['s'])
        right   = self.right   * (held_keys['d'] - held_keys['a'])

        move = (forward + right) * self.speed * time.dt
        self.position += Vec3(move.x, 0, move.z)

        # ----- JUMP / GRAVITY -----
        self.vy -= 0.8 * time.dt
        self.y += self.vy

        if self.y <= 1:
            self.y = 1
            self.vy = 0
            self.on_ground = True

        if held_keys['space'] and self.on_ground:
            self.vy = self.jump_force
            self.on_ground = False

    def hit(self):
        global last_hitter

        if serve_mode:
            return

        if self.hit_zone.intersects(ball).hit:
            last_hitter = "player"
            forward_dir = camera.forward + Vec3(0, 0.7, 0)
            forward_dir = forward_dir.normalized()

            ball.velocity = forward_dir * 10
            bump_effect(ball.position)
            play_bump_animation(self)

    def spike(self):
        global last_hitter

        if serve_mode:
            return

        if self.hit_zone.intersects(ball).hit:
            forward_dir = camera.forward + Vec3(0, -.5, 0)
            forward_dir = forward_dir.normalized()

            ball.velocity = forward_dir * 15
            spike_effect(self.position)
            camera_shake()

player = Player()

# -------------------------------------------
# AI OPPONENT
# -------------------------------------------

class Opponent(Entity):
    def __init__(self, position=(10,1,0)):
        super().__init__(
            model='cube',
            color=color.red,
            scale=(1,2,1),
            position=position,
            collider='box'
        )
        self.speed = 6

        self.hit_zone = Entity(
            parent=self,
            model='cube',
            scale=(1,1,1.5),
            position=(0,1,-1),
            color=color.rgba(255,0,0,40),
            collider='box'
        )

    def update_ai(self):
        if serve_mode:
            return
        if ball.x > 0:

            predicted_x = ball.x + ball.velocity.x * 0.1
            predicted_z = ball.z + ball.velocity.z * 0.1

            target_x = predicted_x
            target_z = predicted_z

            if target_x > self.x:
                self.x += self.speed * time.dt
            else:
                self.x -= self.speed * time.dt

            if target_z > self.z:
                self.z += self.speed * time.dt
            else:
                self.z -= self.speed * time.dt

            if self.hit_zone.intersects(ball).hit:
                global opp_spike, last_hitter
                opp_spike = random.choice([False,True])
                last_hitter = "ai"

                if opp_spike:
                    bump_dir = Vec3(-1, 0.9, random.uniform(-0.3, 0.3)).normalized()
                    ball.velocity = bump_dir * 13
                    spike_effect(self.position)
                    camera_shake()
                else:
                    bump_dir = Vec3(-1, 1, random.uniform(-0.3, 0.3)).normalized()
                    ball.velocity = bump_dir * 9

opponent = Opponent()

# -------------------------------------------
# SERVING SYSTEM
# -------------------------------------------

serve_mode = True
server = "player"

serve_text = Text("Press E to Serve", origin=(0,0), y=0.4, scale=2)

def reset_for_serve():
    global serve_mode
    serve_mode = True
    ball.velocity = Vec3(0,0,0)

    if server == "player":
        player.position = (-10,1,0)
        ball.position = player.position + Vec3(1,3,0)
        serve_text.text = "Press E to Serve"
    else:
        opponent.position = (10,1,0)
        ball.position = opponent.position + Vec3(-1,10,0)
        serve_text.text = "AI Serving..."

    serve_text.enabled = True

def do_serve():
    global serve_mode, server
    serve_mode = False
    serve_text.enabled = False

    if server == "player":
        player.position = (-10,1,0)
        ball.velocity = Vec3(0.5,10,random.uniform(-1,1))
    else:
        opponent.position = (10,1,0)
        ball.velocity = Vec3(-0.5,10,random.uniform(-1,1))

# -------------------------------------------
# INPUT
# -------------------------------------------

def input(key):
    if key == 'left mouse down':
        if player.on_ground:
            player.hit()
        else:
            player.spike()
    if key == 'e' and serve_mode and server == "player":
        do_serve()

# -------------------------------------------
# SCORING
# -------------------------------------------

def award_point(to):
    global player_score, ai_score, server

    if to == "player":
        player_score += 1
        server = "player"
    else:
        ai_score += 1
        server = "ai"

    score_text.text = f"{player_score}    -    {ai_score}"
    reset_for_serve()

# -------------------------------------------
# UPDATE LOOP
# -------------------------------------------

def update():
    global server

    if serve_mode and server == "ai":
        invoke(do_serve, delay=1.2)
        server = "waiting"

    player.update()
    opponent.update_ai()

    ball.velocity.y -= GRAVITY
    ball.position += ball.velocity * time.dt

    if ball.y < 0.1:
        ball.y = 0.5
        ball.velocity.y *= -0.6

    if ball.intersects(net).hit:
        if ball.y <= net.y + net.scale_y/2:
            ball.velocity.x *= -0.5

    if ball.intersects(ground).hit:
        if ball.x < 0:
            award_point("ai")
        else:
            award_point("player")

    elif ball.intersects(out).hit:
        if last_hitter == "ai":
            award_point("player")
        else:
            award_point("ai")

    # -------------------------------
    # UPDATE TRAJECTORY VISUAL LINE
    # -------------------------------
    future_path = predict_trajectory()
    for i, p in enumerate(trajectory_points):
        p.position = future_path[i]
        p.enabled = True

reset_for_serve()

app.run()
