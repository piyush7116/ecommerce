# blog/views.py
from django.shortcuts import render
from django.http import HttpResponse
from .models import Blog

def index(request):
    blogs=Blog.objects.all()
    counts=len(blogs)
    params={'blogs':blogs,'range':counts}
    return render(request,'blog/index.html',params)


def blogpost(request, blogid):
    blog=Blog.objects.get(post_id=blogid)
    myblog={'blog':blog}
    return render(request,'blog/blogpost.html',myblog)