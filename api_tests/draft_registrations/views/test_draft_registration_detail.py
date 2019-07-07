import pytest

from api.base.settings.defaults import API_BASE
from api_tests.nodes.views.test_node_draft_registration_detail import (
    TestDraftRegistrationDetail,
    TestDraftRegistrationUpdate,
    TestDraftRegistrationPatch,
    TestDraftRegistrationDelete,
    TestDraftPreregChallengeRegistrationMetadataValidation
)
from osf.models import DraftNode, Node, NodeLicense
from osf.utils.permissions import ADMIN
from osf_tests.factories import (
    DraftRegistrationFactory,
    AuthUserFactory,
    InstitutionFactory,
    SubjectFactory
)


@pytest.mark.django_db
class TestDraftRegistrationDetailEndpoint(TestDraftRegistrationDetail):
    @pytest.fixture()
    def url_draft_registrations(self, project_public, draft_registration):
        return '/{}draft_registrations/{}/'.format(
            API_BASE, draft_registration._id)

    # Overrides TestDraftRegistrationDetail
    def test_admin_group_member_can_view(self, app, user, draft_registration, project_public,
            schema, url_draft_registrations, group_mem):

        res = app.get(url_draft_registrations, auth=group_mem.auth, expect_errors=True)
        assert res.status_code == 403

    def test_detail_view_returns_editable_fields(self, app, user, draft_registration,
            url_draft_registrations, project_public):

        res = app.get(url_draft_registrations, auth=user.auth, expect_errors=True)
        attributes = res.json['data']['attributes']

        assert attributes['title'] == project_public.title
        assert attributes['description'] == project_public.description
        assert attributes['category'] == project_public.category

        res.json['data']['links']['self'] == url_draft_registrations

        relationships = res.json['data']['relationships']
        assert Node.load(relationships['branched_from']['data']['id']) == draft_registration.branched_from

        assert 'affiliated_institutions' in relationships
        assert 'subjects' in relationships
        assert 'contributors' in relationships

    def test_detail_view_returns_editable_fields_no_specified_node(self, app, user):

        draft_registration = DraftRegistrationFactory(initiator=user, branched_from=None)
        url = '/{}draft_registrations/{}/'.format(
            API_BASE, draft_registration._id)

        res = app.get(url, auth=user.auth, expect_errors=True)
        attributes = res.json['data']['attributes']

        assert attributes['title'] == 'Untitled'
        assert attributes['description'] == ''
        assert attributes['category'] == ''
        assert attributes['node_license'] is None

        res.json['data']['links']['self'] == url
        relationships = res.json['data']['relationships']
        assert DraftNode.load(relationships['branched_from']['data']['id']) == draft_registration.branched_from

        assert 'affiliated_institutions' in relationships
        assert 'subjects' in relationships
        assert 'contributors' in relationships

    def test_draft_registration_perms_checked_on_draft_not_node(self, app, user, project_public,
            draft_registration, url_draft_registrations):

        # Admin on node and draft
        assert project_public.has_permission(user, ADMIN) is True
        assert draft_registration.has_permission(user, ADMIN) is True
        res = app.get(url_draft_registrations, auth=user.auth)
        assert res.status_code == 200

        # Admin on node but not draft
        node_admin = AuthUserFactory()
        project_public.add_contributor(node_admin, ADMIN)
        assert project_public.has_permission(node_admin, ADMIN) is True
        assert draft_registration.has_permission(node_admin, ADMIN) is False
        res = app.get(url_draft_registrations, auth=node_admin.auth, expect_errors=True)
        assert res.status_code == 403

        # Admin on draft but not node
        draft_admin = AuthUserFactory()
        draft_registration.add_contributor(draft_admin, ADMIN)
        assert project_public.has_permission(draft_admin, ADMIN) is False
        assert draft_registration.has_permission(draft_admin, ADMIN) is True
        res = app.get(url_draft_registrations, auth=draft_admin.auth)
        assert res.status_code == 200


class TestUpdateEditableFieldsTestCase:
    @pytest.fixture()
    def license(self):
        return NodeLicense.objects.get(license_id='GPL3')

    @pytest.fixture()
    def copyright_holders(self):
        return ['Richard Stallman']

    @pytest.fixture()
    def year(self):
        return '2019'

    @pytest.fixture()
    def subject(self):
        return SubjectFactory()

    @pytest.fixture()
    def institution_one(self):
        return InstitutionFactory()

    @pytest.fixture()
    def title(self):
        return 'California shrub oak'

    @pytest.fixture()
    def description(self):
        return 'Quercus berberidifolia'

    @pytest.fixture()
    def category(self):
        return 'software'

    @pytest.fixture()
    def editable_fields_payload(self, draft_registration, license, copyright_holders,
            year, institution_one, title, description, category, subject,):
        return {
            'data': {
                'id': draft_registration._id,
                'type': 'draft_registrations',
                'attributes': {
                    'title': title,
                    'description': description,
                    'category': category,
                    'node_license': {
                        'year': year,
                        'copyright_holders': copyright_holders
                    },
                    'tags': ['oak', 'tree'],
                },
                'relationships': {
                    'license': {
                        'data': {
                            'type': 'licenses',
                            'id': license._id
                        }
                    },
                    'affiliated_institutions': {
                        'data': [
                            {'type': 'institutions', 'id': institution_one._id}
                        ]
                    },
                    'subjects': {
                        'data': [
                            {'id': subject._id, 'type': 'subjects'},
                        ]
                    }
                }
            }
        }


@pytest.mark.django_db
class TestDraftRegistrationUpdateWithNode(TestDraftRegistrationUpdate, TestUpdateEditableFieldsTestCase):
    @pytest.fixture()
    def url_draft_registrations(self, project_public, draft_registration):
        return '/{}draft_registrations/{}/'.format(
            API_BASE, draft_registration._id)

    def test_update_editable_fields(self, app, url_draft_registrations, draft_registration, license, copyright_holders,
            year, institution_one, user, title, description, category, subject, editable_fields_payload):
        user.affiliated_institutions.add(institution_one)

        res = app.put_json_api(
            url_draft_registrations, editable_fields_payload,
            auth=user.auth, expect_errors=True)
        assert res.status_code == 200
        attributes = res.json['data']['attributes']

        assert attributes['title'] == title
        assert attributes['description'] == description
        assert attributes['category'] == category
        assert attributes['node_license']['year'] == year
        assert attributes['node_license']['copyright_holders'] == copyright_holders
        assert set(attributes['tags']) == set(['oak', 'tree'])

        relationships = res.json['data']['relationships']
        assert relationships['license']['data']['id'] == license._id

        # TODO verify links
        subjects = draft_registration.subjects.values_list('id', flat=True)
        assert len(subjects) == 1
        assert subjects[0] == subject.id
        assert 'draft_registrations/{}/subjects'.format(draft_registration._id) in relationships['subjects']['links']['related']['href']
        assert 'draft_registrations/{}/relationships/subjects'.format(draft_registration._id) in relationships['subjects']['links']['self']['href']

        affiliated_institutions = draft_registration.affiliated_institutions.values_list('id', flat=True)
        assert len(affiliated_institutions) == 1
        assert affiliated_institutions[0] == institution_one.id
        assert 'draft_registrations/{}/institutions'.format(draft_registration._id) in relationships['affiliated_institutions']['links']['related']['href']
        assert 'draft_registrations/{}/relationships/institutions'.format(draft_registration._id) in relationships['affiliated_institutions']['links']['self']['href']

        assert 'draft_registrations/{}/contributors'.format(draft_registration._id) in relationships['contributors']['links']['related']['href']

    def test_registration_metadata_must_be_supplied(
            self, app, user, payload, url_draft_registrations):
        payload['data']['attributes'] = {}

        res = app.put_json_api(
            url_draft_registrations,
            payload, auth=user.auth,
            expect_errors=True)
        # Override - not required
        assert res.status_code == 200

    # def test_invalid_editable_field_updates

    # def test node perms

    # def test cannot update node, schema,


@pytest.mark.django_db
class TestDraftRegistrationUpdateWithDraftNode(TestDraftRegistrationUpdate):
    @pytest.fixture()
    def url_draft_registrations(self, project_public, draft_registration):
        return '/{}draft_registrations/{}/'.format(
            API_BASE, draft_registration._id)

    @pytest.fixture()
    def draft_registration(self, user, project_public, schema):
        return DraftRegistrationFactory(
            initiator=user,
            registration_schema=schema,
            branched_from=None
        )


class TestDraftRegistrationPatchNew(TestDraftRegistrationPatch):
    @pytest.fixture()
    def url_draft_registrations(self, project_public, draft_registration):
        # Overrides TestDraftRegistrationPatch
        return '/{}draft_registrations/{}/'.format(
            API_BASE, draft_registration._id)


class TestDraftRegistrationDelete(TestDraftRegistrationDelete):
    @pytest.fixture()
    def url_draft_registrations(self, project_public, draft_registration):
        # Overrides TestDraftRegistrationDelete
        return '/{}draft_registrations/{}/'.format(
            API_BASE, draft_registration._id)


class TestDraftPreregChallengeRegistrationMetadataValidationNew(TestDraftPreregChallengeRegistrationMetadataValidation):
    @pytest.fixture()
    def url_draft_registrations(
            self, project_public,
            draft_registration_prereg):
        return '/{}draft_registrations/{}/'.format(
            API_BASE, draft_registration_prereg._id)