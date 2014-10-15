import re
import unittest
from flask import url_for

from models import Tags, User, Shreds
from . import BasicTestCase


class TaggingTest(BasicTestCase):
    def setUp(self):
        self.client.post(url_for("fixtures.reset_db"))
        self.client.post(url_for("fixtures.create_base_tags"))

    def test_index_not_logged(self):
        res = self.client.get(url_for("index"))

        self.assert200(res)
        body = res.get_data(as_text=True)
        self.assertTrue("warm-welcome" in body)
        self.assertTrue(url_for("social.auth", backend="facebook") in body)
        self.assertTrue(url_for("social.auth", backend="twitter") in body)
        self.assertTrue(
            url_for("social.auth", backend="google-oauth2") in body)
        self.assertTrue(
            url_for("social.auth", backend="vk-oauth2") in body)

    def test_index_logged(self):
        self.create_user_and_login("user")

        res = self.client.get(url_for("index"))

        self.assert200(res)
        body = res.get_data(as_text=True)

        self.assertFalse("warm-welcome" in body)
        self.assertFalse(url_for("social.auth", backend="facebook") in body)
        self.assertFalse(url_for("social.auth", backend="twitter") in body)
        self.assertFalse(
            url_for("social.auth", backend="google-oauth2") in body)
        self.assertFalse(
            url_for("social.auth", backend="vk-oauth2") in body)

        for tag in Tags.objects(is_base=True):
            self.assertTrue(tag.title.lower() in body.lower())
            self.assertTrue(tag.category.lower() in body.lower())
            if tag.hotkey:
                self.assertTrue(tag.hotkey in body.lower())

    def test_no_more_tasks(self):
        self.create_user_and_login("user")

        res = self.client.get(url_for("next"))

        self.assert200(res)
        body = res.get_data(as_text=True)

        self.assertFalse("shred_id" in body)
        self.assertFalse(url_for("next") in body)

    def test_has_some_tasks(self):
        self.create_user_and_login("user")

        self.client.post(url_for("fixtures.create_shreds"))

        res = self.client.get(url_for("next"))
        self.assert200(res)
        body = res.get_data(as_text=True)

        self.assertTrue("shred_id" in body)
        self.assertTrue(url_for("next") in body)

        for tag in Tags.objects(is_base=True):
            self.assertTrue(
                tag.title.capitalize().encode('unicode-escape') in body)

    def test_user_tags_in_task(self):
        self.create_user_and_login("user")

        self.client.post(url_for("fixtures.create_shreds"))

        user = User.objects.get(username="user")
        admin = User.objects.get(username="admin")
        user_tag = "foobar"
        another_user_tag = "barfoo"

        Tags.objects.create(title=user_tag, is_base=False,
                            created_by=user)
        Tags.objects.create(title=another_user_tag, is_base=False,
                            created_by=admin)

        user.tags = [user_tag]
        admin.tags = [another_user_tag]
        user.save()
        admin.save()

        res = self.client.get(url_for("next"))
        self.assert200(res)
        body = res.get_data(as_text=True)

        self.assertTrue(
            user_tag.capitalize().encode('unicode-escape') in body)
        pos = body.index(user_tag.capitalize().encode('unicode-escape'))

        self.assertFalse(
            another_user_tag.capitalize().encode('unicode-escape') in body)

        for tag in Tags.objects(is_base=True):
            tag = tag.title.capitalize().encode('unicode-escape')
            self.assertTrue(tag in body)

            self.assertTrue(body.index(tag) < pos)

    def test_tags_ordering_in_task(self):
        self.create_user_and_login("user")
        self.client.post(url_for("fixtures.create_shreds"))

        first_tag = Tags.objects[0]
        new_first_tag = Tags.objects[1]

        new_first_tag.usages = 100
        new_first_tag.save()

        res = self.client.get(url_for("next"))
        self.assert200(res)
        body = res.get_data(as_text=True)

        self.assertTrue(
            body.index(first_tag.title.capitalize().encode('unicode-escape')) >
            body.index(
                new_first_tag.title.capitalize().encode('unicode-escape'))
        )

    def test_auto_tags(self):
        self.create_user_and_login("user")
        self.client.post(url_for("fixtures.create_shreds"))

        tag = Tags.objects.create(title="my new tag",
                                  synonyms=["foobar_synonym"],
                                  is_base=True)

        res = self.client.get(url_for("next"))
        self.assert200(res)
        body = res.get_data(as_text=True)

        self.assertEquals(
            body.count(tag.title.capitalize().encode('unicode-escape')), 1)

        Shreds.objects.update(add_to_set__tags_suggestions=["foobar_synonym"])

        res = self.client.get(url_for("next"))
        self.assert200(res)
        body = res.get_data(as_text=True)

        self.assertEquals(
            body.count(tag.title.capitalize().encode('unicode-escape')), 2)

    def parse_shred_id(self, body):
        pattern = r'id="shred_id".*?"([^"]*)"'

        m = re.search(pattern, body)
        return m.group(1)

    def test_skipping(self):
        self.create_user_and_login("user")
        self.client.post(url_for("fixtures.create_shreds"))

        res = self.client.get(url_for("next"))
        self.assert200(res)
        body = res.get_data(as_text=True)

        current_shred = first_shred = self.parse_shred_id(body)

        for i in xrange(9):
            res = self.client.post(url_for("skip"),
                                   data={"_id": current_shred},
                                   follow_redirects=True)

            body = res.get_data(as_text=True)
            self.assert200(res)

            current_shred = self.parse_shred_id(body)
            self.assertNotEqual(current_shred, first_shred)

        raise unittest.SkipTest("WIP")

        res = self.client.post(url_for("skip"),
                               data={"_id": current_shred},
                               follow_redirects=True)

        body = res.get_data(as_text=True)
        self.assert200(res)

        current_shred = self.parse_shred_id(body)
        self.assertEqual(current_shred, first_shred)
