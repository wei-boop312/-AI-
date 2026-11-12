import unittest
from io import BytesIO
from uuid import uuid4
from PIL import Image
from pydantic import ValidationError
from fastapi.testclient import TestClient
from visual_platform.domain.schemas import QuoteRequest,canonical_hash
from visual_platform.imaging.normalize import normalize
from visual_platform.domain.compliance import evaluate
from visual_platform.api.main import app

class ContractTests(unittest.TestCase):
    def request(self):
        return dict(product_id=str(uuid4()),source_asset_version_id=str(uuid4()),generation=dict(type='scene',prompt='test',output=dict(width=100,height=100),protection_mode='none'),targets=[dict(platform='amazon',marketplace='US',category='generic',image_type='MAIN')])
    def test_reject_extra_identity_and_coercion(self):
        d=self.request(); d['user_id']=str(uuid4())
        with self.assertRaises(ValidationError): QuoteRequest.model_validate(d)
        d=self.request(); d['generation']['output']['width']=True
        with self.assertRaises(ValidationError): QuoteRequest.model_validate(d)
    def test_hash_defaults(self):
        d=self.request(); a=QuoteRequest.model_validate(d)
        d['generation']['regions']=[]; d['generation']['output']['format']='png'
        self.assertEqual(canonical_hash(a),canonical_hash(QuoteRequest.model_validate(d)))
    def test_normalization_strips_exif_and_flattens_alpha(self):
        im=Image.new('RGBA',(8,5),(255,0,0,0)); exif=Image.Exif(); exif[270]='private'
        b=BytesIO(); im.save(b,'PNG',exif=exif)
        with Image.open(BytesIO(normalize(b.getvalue()))) as result:
            self.assertEqual(result.mode,'RGB'); self.assertEqual(result.getpixel((0,0)),(255,255,255)); self.assertFalse(result.getexif())
    def test_orientation(self):
        im=Image.new('RGB',(8,5)); exif=Image.Exif(); exif[274]=6
        b=BytesIO(); im.save(b,'JPEG',exif=exif)
        with Image.open(BytesIO(normalize(b.getvalue()))) as result: self.assertEqual(result.size,(5,8))
    def test_rule_does_not_auto_pass(self):
        r=evaluate('a'*64,['amazon'],evidence_verified=True,analysis_complete=True)
        self.assertEqual(r['per_platform'][0]['status'],'manual_review')
    def test_health_is_honest(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/v1/health/live').status_code,200)
            self.assertEqual(client.get('/api/v1/health/ready').status_code,503)
