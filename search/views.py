from django.shortcuts import render
import json
from django.views.generic.base import View
from search.models import Lagou
from django.http import HttpResponse
from elasticsearch import Elasticsearch
client = Elasticsearch(hosts=["127.0.0.1"])
from datetime import datetime
import redis
redis_cli = redis.StrictRedis(charset='UTF-8', decode_responses=True,unix_socket_path=None)
# Create your views here.


class IndexView(View):
    def get(self,request):
        topn_search = redis_cli.zrevrangebyscore("search_keyword_set", "+inf", "-inf", start=0, num=5)
        return render(request, "index.html",{"topn_search":topn_search})

class SearchSuggest(View):
    #搜索智能提示
    def get(self,request):
        key_words = request.GET.get('s','')
        re_datas = []
        if key_words:
            s = Lagou.search()
            s = s.suggest('suggest',key_words,completion={
                "field":"suggest","fuzzy":{
                    "fuzziness":2
                },
                "size":10
            })
            suggestions = s.execute()
            for match in suggestions.suggest.suggest[0].options:
                source = match._source
                re_datas.append(source["title"])
        return HttpResponse(json.dumps(re_datas),content_type="application/json")

class SearchView(View):
    def get(self,request):
        key_words = request.GET.get("q","")
        redis_cli.zincrby("search_keyword_set",key_words)
        topn_search = redis_cli.zrevrangebyscore("search_keyword_set","+inf","-inf",start=0,num=5)
        page = request.GET.get("q","2")
        try:
            page = int(page)
        except:
            page = 1

        start_time = datetime.now()
        response = client.search(
            index="lagou",
            body={
                "query":{
                    "multi_match":{
                        "query":key_words,
                        "fields":["tags","title","content"]
                    }
                },
                "from":(page-1)*10,
                "size":10,
                "highlight":{
                    "pre_tags": ['<span class="keyWord">'],
                    "post_tags": ['</span>'],
                    "fields":{

                        "title":{},
                        "content":{},
                    }

                }

            }

        )
        end_time = datetime.now()
        last_time = (end_time - start_time).total_seconds()
        lagou_count = redis_cli.get("lagou_count")
        total_nums = response["hits"]["total"]
        if (page%10) > 0:
            page_nums = int(total_nums/10 + 1)
        else:
            page_nums = int(total_nums/10)
        hit_list = []
        for hit in response["hits"]["hits"]:
            hit_dict = {}
            if "highlight" in hit.keys():
                if "title" in hit["highlight"]:
                     hit_dict["title"] = hit["highlight"]["title"]
                else:
                     hit_dict["title"] = hit["_source"]["title"]

                if "job_desc" in hit["highlight"]:
                    hit_dict["job_desc"] = hit["highlight"]["job_desc"]

                else:
                    hit_dict["job_desc"] = hit["_source"]["job_desc"]
            else:
                hit_dict["job_desc"] = hit["_source"]["job_desc"]
                hit_dict["title"] = hit["_source"]["title"]

            hit_dict["publish_time"] = hit["_source"]["publish_time"]
            hit_dict["url"] = hit["_source"]["url"]
            hit_dict["score"] = hit["_score"]
            hit_list.append(hit_dict)

        return render(request,"result.html", {"page":page,
                                              "all_hits":hit_list,
                                              "key_words":key_words,
                                              "total_nums":total_nums,
                                              "page_nums":page_nums,
                                              "last_seconds":last_time,
                                              "lagou_count":lagou_count,
                                              "topn_search":topn_search})