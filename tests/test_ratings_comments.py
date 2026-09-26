import pytest


@pytest.mark.django_db
def test_rating_average_and_update(api, user, make_user, make_video):
    v = make_video()
    api.force_authenticate(user)
    assert api.post(f"/api/videos/{v.id}/rate/", {"score": 5}, format="json").status_code == 200
    api.force_authenticate(make_user("b@example.com"))
    r = api.post(f"/api/videos/{v.id}/rate/", {"score": 3}, format="json")
    assert r.data["avg_rating"] == 4.0
    assert r.data["ratings_count"] == 2

    # rating again updates instead of duplicating
    r = api.post(f"/api/videos/{v.id}/rate/", {"score": 1}, format="json")
    assert r.data["ratings_count"] == 2
    assert r.data["avg_rating"] == 3.0


@pytest.mark.django_db
def test_invalid_score(api, user, make_video):
    v = make_video()
    api.force_authenticate(user)
    assert api.post(f"/api/videos/{v.id}/rate/", {"score": 6}, format="json").status_code == 400


@pytest.mark.django_db
def test_comments(api, user, make_video):
    v = make_video()
    assert api.post(f"/api/videos/{v.id}/comments/", {"body": "hi"}, format="json").status_code == 401
    api.force_authenticate(user)
    r = api.post(f"/api/videos/{v.id}/comments/", {"body": "nice"}, format="json")
    assert r.status_code == 201
    r = api.get(f"/api/videos/{v.id}/comments/")
    assert r.data["count"] == 1
    assert r.data["results"][0]["body"] == "nice"
