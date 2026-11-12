"""Official SDK over offline MockTransport, not a mocked SDK method."""
import asyncio
import base64
import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx
from PIL import Image
from visual_platform.providers.gemini import GeminiProvider,MODEL
from visual_platform.providers.contract import ProviderUncertain

class GeminiContracts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.providers=[];self.calls=[]
        stream=BytesIO();Image.new('RGB',(256,256),'white').save(stream,'PNG');self.png=stream.getvalue();self.sha=hashlib.sha256(self.png).hexdigest()
        self.facts={'schema_version':1,'analysis_complete':True,'image_width':256,'image_height':256,'text_items':[],'logo_items':[],'watermark_items':[],'background':{'classification':'white','confidence':0.95},'product_extent':{'bbox':[10,10,240,240],'confidence':0.95},'uncertainties':[]}
    async def asyncTearDown(self):
        for provider in self.providers:await provider.aclose()
        self.temp.cleanup()
    def response(self,facts=None,*,finish='STOP'):
        return {'candidates':[{'content':{'role':'model','parts':[{'text':json.dumps(self.facts if facts is None else facts)}]},'finishReason':finish}],'responseId':'response-xyz','modelVersion':MODEL,'usageMetadata':{'promptTokenCount':120,'candidatesTokenCount':80,'thoughtsTokenCount':20,'totalTokenCount':220}}
    def provider(self,handler=None):
        async def route(request):
            self.calls.append(request)
            if handler:
                value=handler(request)
                return await value if asyncio.iscoroutine(value) else value
            return httpx.Response(200,json=self.response())
        provider=GeminiProvider('contract-key',Path(self.temp.name),transport=httpx.MockTransport(route));self.providers.append(provider);return provider
    async def submit(self,provider,intent=None,**kwargs):
        return await provider.submit(intent or uuid4(),self.png,expected_sha256=kwargs.get('sha',self.sha),width=kwargs.get('width',256),height=256)
    async def test_real_sdk_request_model_final_bytes_schema_and_usage(self):
        provider=self.provider();receipt=await self.submit(provider);request=self.calls[0];body=json.loads(request.content)
        self.assertEqual(str(request.url),'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent');self.assertEqual(request.headers['x-goog-api-key'],'contract-key')
        inline=body['contents'][0]['parts'][1]['inlineData'];self.assertEqual(inline['mime_type'],'image/png');self.assertEqual(base64.urlsafe_b64decode(inline['data']),self.png)
        config=body['generationConfig'];self.assertEqual(config['responseMimeType'],'application/json');self.assertIn('image_width',config['responseJsonSchema']['properties']);self.assertNotIn('compliant',config['responseJsonSchema']['properties']);self.assertNotIn('tools',body)
        result=provider.fetch_facts(receipt.provider_id);self.assertEqual(result['final_sha256'],self.sha);self.assertFalse(result['manual_review_required']);self.assertEqual(result['provider_response_id'],'response-xyz');self.assertEqual(result['usage']['total_token_count'],220);self.assertIsNone(result['cost']['money_amount']);self.assertIsNone(result['cost']['currency']);self.assertEqual(len(self.calls),1)
        self.assertNotIn('contract-key',''.join(path.read_text() for path in Path(self.temp.name).iterdir()))
    async def test_sdk_429_and_503_never_retry(self):
        for status in (429,503):
            provider=self.provider(lambda _:httpx.Response(status,json={'error':{'code':status,'message':'sensitive contract-key','status':'RESOURCE_EXHAUSTED' if status==429 else 'UNAVAILABLE'}}));intent=uuid4();before=len(self.calls)
            with self.assertRaises(ProviderUncertain) as caught:await self.submit(provider,intent)
            self.assertNotIn('contract-key',str(caught.exception));self.assertEqual(len(self.calls)-before,1)
            with self.assertRaises(ProviderUncertain):await self.submit(self.provider(),intent)
            self.assertEqual(len(self.calls)-before,1)
    async def test_sdk_timeout_retains_intent_and_sanitizes(self):
        def timeout(request):raise httpx.ReadTimeout('contract-key '+str(request.url))
        provider=self.provider(timeout);intent=uuid4()
        with self.assertRaises(ProviderUncertain) as caught:await self.submit(provider,intent)
        self.assertNotIn('contract-key',str(caught.exception))
        with self.assertRaises(ProviderUncertain):await self.submit(provider,intent)
        self.assertEqual(len(self.calls),1)
    async def test_sdk_continuation_does_not_issue_second_request(self):
        value=self.response(finish='CONTINUATION');value['continuationToken']='do-not-continue'
        provider=self.provider(lambda _:httpx.Response(200,json=value));receipt=await self.submit(provider)
        self.assertTrue(provider.fetch_facts(receipt.provider_id)['manual_review_required']);self.assertEqual(len(self.calls),1)
    async def test_truncated_and_safety_results_degrade(self):
        for finish in ('MAX_TOKENS','SAFETY','RECITATION','OTHER'):
            provider=self.provider(lambda _,f=finish:httpx.Response(200,json=self.response(finish=f)));receipt=await self.submit(provider)
            result=provider.fetch_facts(receipt.provider_id);self.assertFalse(result['facts']['analysis_complete']);self.assertTrue(result['manual_review_required'])
    async def test_prompt_block_and_missing_candidate_degrade(self):
        for value in ({'promptFeedback':{'blockReason':'SAFETY'}},{'candidates':[]},{}):
            provider=self.provider(lambda _,v=value:httpx.Response(200,json=v));receipt=await self.submit(provider);self.assertTrue(provider.fetch_facts(receipt.provider_id)['manual_review_required'])
    async def test_schema_missing_extra_compliance_and_invalid_bbox_degrade(self):
        cases=[]
        missing=copy.deepcopy(self.facts);del missing['background'];cases.append(missing)
        extra=copy.deepcopy(self.facts);extra['compliant']=True;cases.append(extra)
        bad_bbox=copy.deepcopy(self.facts);bad_bbox['product_extent']['bbox']=[0,0,999,999];cases.append(bad_bbox)
        wrong=copy.deepcopy(self.facts);wrong['image_width']=512;cases.append(wrong)
        confidence=copy.deepcopy(self.facts);confidence['background']['confidence']=1.1;cases.append(confidence)
        numeric=copy.deepcopy(self.facts);numeric['image_height']='256';cases.append(numeric)
        for facts in cases:
            provider=self.provider(lambda _,f=facts:httpx.Response(200,json=self.response(f)));receipt=await self.submit(provider);result=provider.fetch_facts(receipt.provider_id)
            self.assertTrue(result['manual_review_required']);self.assertEqual(result['facts']['image_width'],256);self.assertEqual(result['facts']['uncertainties'],['gemini_facts_schema_or_dimensions_invalid'])
    async def test_low_confidence_preserves_observations_but_degrades(self):
        facts=copy.deepcopy(self.facts);facts['text_items']=[{'text':'brand','bbox':[10,10,80,40],'origin':'on_product','confidence':0.5}]
        provider=self.provider(lambda _:httpx.Response(200,json=self.response(facts)));receipt=await self.submit(provider);result=provider.fetch_facts(receipt.provider_id)
        self.assertEqual(result['facts']['text_items'][0]['text'],'brand');self.assertIn('gemini_low_confidence',result['facts']['uncertainties']);self.assertFalse(result['facts']['analysis_complete'])
    async def test_malformed_json_and_function_call_degrade(self):
        malformed=self.response();malformed['candidates'][0]['content']['parts']=[{'text':'{"schema_version":'}]
        function=self.response();function['candidates'][0]['content']['parts']=[{'functionCall':{'name':'declare_compliant','args':{}}}]
        for value in (malformed,function):
            provider=self.provider(lambda _,v=value:httpx.Response(200,json=v));receipt=await self.submit(provider);self.assertTrue(provider.fetch_facts(receipt.provider_id)['manual_review_required'])
    async def test_preflight_hash_dimensions_and_non_png_do_not_submit(self):
        provider=self.provider()
        for args in ({'sha':'a'*64},{'width':100}):
            with self.assertRaises(ValueError):await self.submit(provider,**args)
        with self.assertRaises(ValueError):await provider.submit(uuid4(),b'not PNG',expected_sha256=hashlib.sha256(b'not PNG').hexdigest(),width=256,height=256)
        self.assertEqual(self.calls,[]);self.assertEqual(list(Path(self.temp.name).iterdir()),[])
    async def test_concurrent_same_intent_and_restart_only_one_post(self):
        provider=self.provider();intent=uuid4();results=await asyncio.gather(self.submit(provider,intent),self.submit(self.provider(),intent),return_exceptions=True)
        self.assertEqual(sum(isinstance(value,ProviderUncertain) for value in results),1);self.assertEqual(len(self.calls),1)
        with self.assertRaises(ProviderUncertain):await self.submit(self.provider(),intent)
        self.assertEqual(len(self.calls),1)
    async def test_cancel_after_request_prevents_resubmit(self):
        entered=asyncio.Event()
        async def block(request):entered.set();await asyncio.Event().wait()
        provider=self.provider(block);intent=uuid4();task=asyncio.create_task(self.submit(provider,intent));await asyncio.wait_for(entered.wait(),5);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        with self.assertRaises(ProviderUncertain):await self.submit(self.provider(),intent)
        self.assertEqual(len(self.calls),1)
    async def test_unknown_usage_and_no_response_id_not_invented(self):
        value=self.response();del value['usageMetadata'];del value['responseId'];provider=self.provider(lambda _:httpx.Response(200,json=value));receipt=await self.submit(provider);result=provider.fetch_facts(receipt.provider_id)
        self.assertIsNone(result['usage']);self.assertIsNone(result['provider_response_id']);self.assertTrue(receipt.provider_id.startswith('gemini-'))
    async def test_redirect_is_not_followed(self):
        provider=self.provider(lambda _:httpx.Response(302,headers={'location':'https://evil.example/steal'}))
        with self.assertRaises(ProviderUncertain):await self.submit(provider)
        self.assertEqual(len(self.calls),1)
    async def test_fetch_is_local_and_corrupt_archive_never_calls_again(self):
        provider=self.provider();receipt=await self.submit(provider)
        for _ in range(3):self.assertEqual(provider.fetch_facts(receipt.provider_id)['final_sha256'],self.sha)
        next(Path(self.temp.name).glob('*.facts.json')).write_text('{}')
        with self.assertRaises(ProviderUncertain):provider.fetch_facts(receipt.provider_id)
        self.assertEqual(len(self.calls),1)
    async def test_oversized_and_compressed_body_fail_without_retry(self):
        import gzip
        oversized=json.dumps({'padding':'X'*(1024*1024),'candidates':self.response()['candidates']}).encode()
        for response in (httpx.Response(200,stream=httpx.ByteStream(oversized)),httpx.Response(200,stream=httpx.ByteStream(gzip.compress(b'{}')),headers={'content-encoding':'gzip'})):
            provider=self.provider(lambda _,r=response:r);before=len(self.calls)
            with self.assertRaises(ProviderUncertain):await self.submit(provider)
            self.assertEqual(len(self.calls)-before,1)
    async def test_multiple_candidates_and_unspecified_prompt_feedback(self):
        multiple=self.response();multiple['candidates']*=2
        provider=self.provider(lambda _:httpx.Response(200,json=multiple));receipt=await self.submit(provider);self.assertTrue(provider.fetch_facts(receipt.provider_id)['manual_review_required'])
        value=self.response();value['promptFeedback']={'blockReason':'BLOCKED_REASON_UNSPECIFIED'}
        provider=self.provider(lambda _:httpx.Response(200,json=value));receipt=await self.submit(provider);self.assertFalse(provider.fetch_facts(receipt.provider_id)['manual_review_required'])
    async def test_environment_cannot_redirect_key_or_switch_backend(self):
        with patch.dict('os.environ',{'GOOGLE_GEMINI_BASE_URL':'https://evil.example','GOOGLE_GENAI_USE_VERTEXAI':'true','GOOGLE_GENAI_USE_ENTERPRISE':'true'}):
            provider=self.provider();await self.submit(provider)
        self.assertEqual(self.calls[0].url.host,'generativelanguage.googleapis.com');self.assertEqual(len(self.calls),1)
    async def test_checked_in_schema_matches_sdk_request_contract(self):
        from visual_platform.domain.facts import Facts
        root=Path(__file__).resolve().parents[2]
        self.assertEqual(json.loads((root/'contracts/facts.schema.json').read_text()),Facts.model_json_schema())
