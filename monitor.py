from building import map_detected_buildings
from camera import poll_frame_data
from detection import detect_markers
from hud import draw_monitor_window, draw_status_window
from image import buffer_to_array, sharpen_and_rotate_image

while True:
    frames = poll_frame_data()
    for frame in frames:
        camera_id, image = frame
        ir_image = sharpen_and_rotate_image(buffer_to_array(image))
        corners, ids, rejectedImgPoints = detect_markers(ir_image)
        buildingDict = map_detected_buildings(camera_id, ids, corners)
        draw_monitor_window(ir_image, corners, rejectedImgPoints, camera_id)
        draw_status_window(buildingDict, camera_id)
