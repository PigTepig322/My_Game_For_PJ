from ursina import *
from ursina.shaders import lit_with_shadows_shader
from ursina.prefabs.first_person_controller import FirstPersonController
app = Ursina()
player = FirstPersonController(collider='box',position=(0,1.25,0))
ground=Entity(model='cube',collider='mesh',scale=(100,1,100),position=(1,1,1),texture='grass')
dragonight=Entity(model='h1',scale=25,position=(10,8.7,1),collider='box')
dragonight.shader=lit_with_shadows_shader
app.run()
