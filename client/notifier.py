import pyautogui
import math
import time

def notify(radius=100, duration=2, steps=100):
    """
    Notify by drawing a circle around the current mouse position.
    
    Args:
        radius: Radius of the circle in pixels
        duration: Duration of the animation in seconds
        steps: Number of steps for the circle animation
    """
    # Get current mouse position
    x, y = pyautogui.position()
    
    # Calculate time per step
    time_per_step = duration / steps
    
    # Draw a circle
    for i in range(steps):
        # Calculate angle
        angle = (i / steps) * 2 * math.pi
        
        # Calculate new position
        new_x = x + radius * math.cos(angle)
        new_y = y + radius * math.sin(angle)
        
        # Move mouse
        pyautogui.moveTo(new_x, new_y, duration=time_per_step)
    
    # Return to original position
    pyautogui.moveTo(x, y, duration=0.1)