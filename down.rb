#!/usr/bin/env ruby

%w( rubygems sinatra uri net/http erb ).each { |g| require g }
include ERB::Util

layout { File.read('views/layout.erb') }

def show(template, title="Down for everyone or just me?")
  @title = title
  erb(template)
end

get '/' do
  show :home
end

get '/q' do
  user_domain = params[:domain]
  @domain = user_domain

  actual_domain = params[:domain]
  actual_domain = "http://#{@domain}" unless @domain =~ /^http:\/\//
  @actual_domain = h(actual_domain)

  uri = valid_uri(actual_domain)
  
  if uri == :invalid
    redirect '/huh'
  elsif is_up?(uri)
    show(:up, "It's just you.")
  else
    show(:down, "Panic!")
  end
end

get '/huh' do
  show(:huh, "Huh?")
end

private

  def valid_uri(domain)
    uri = nil
    code = nil
    
    begin 
      uri = URI.parse(domain)
    rescue Exception
      return :invalid
    else
      return :invalid unless uri.class == URI::HTTP
    end
    
    uri
  end
  
  def is_up?(uri)  
    puts "URI: #{uri.host}:#{uri.port} - #{uri}"
    code = nil
      
    begin
      Net::HTTP.start(uri.host, uri.port) do |http|
        code = http.request_head("/").code
      end      
    rescue Exception => e
      return false
    else
      if code =~ /(200|301|302)/
        return true
      else
        return false
      end
    end
    
    false  
  end