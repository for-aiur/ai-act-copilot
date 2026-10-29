"""Example: identify people from a camera image against a stored face gallery."""


def identify_person(camera_frame, face_model, enrolled_gallery):
    face_embedding = face_model.encode(camera_frame)
    identity, similarity = enrolled_gallery.nearest_identity(face_embedding)
    return identity if similarity > 0.85 else None
