#!/usr/bin/env ruby

%w( rubygems sinatra uri net/http erb timeout ).each { |g| require g }

include ERB::Util

def show(template, title="Down for everyone or just me?")
  @title = title
  erb template
end

get '/' do
  show :home
end

get '/q' do
  domain = params[:domain]
  domain.gsub!('/http://', '')
  redirect "/#{domain}"
end

['/:domain', '/:domain/', '/:www.:domain', '/:www.:domain/', '/:www.:domain.:ext', '/:www.:domain.:ext/'].each do |route|
  get route do
    actual_domain = params[:domain]
    
    actual_domain = "#{params[:www]}.#{actual_domain}" if params[:www]          
    actual_domain = "#{actual_domain}.#{params[:ext]}" if params[:ext]
    
    if params[:format] != 'html' && params[:format] != nil
      actual_domain = "#{actual_domain}.#{params[:format]}"
    else
      actual_domain = "#{actual_domain}.com" unless actual_domain =~ /\.\w+/
    end
    
    before_http = actual_domain
    @domain = h(before_http)
    
    actual_domain = "http://#{actual_domain}" unless actual_domain =~ /^http:\/\//
    uri = valid_uri(actual_domain)
    
    if actual_domain =~ /downforeveryoneorjustme\.com/
      show(:hurr, "Well, yes.")
    elsif uri == :invalid
      show(:huh, "Huh?")
    elsif is_up?(uri)
      show(:up, "It's just you.")
    else
      show(:down, "It's not just you!")
    end
  end
end

[404, 500].each do |route|
  get route do 
    show(:huh, "Huh?")
  end
end

private

  def valid_uri(domain)
    uri = nil
    
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
    code = nil
      
    begin
      Timeout::timeout(4) {
        Net::HTTP.start(uri.host, uri.port) do |http|
          http.read_timeout = 3
          code = http.request_head('/', { 'User-Agent' => 'downforeveryoneorjustme.com' }).code
        end
      }
    rescue Timeout::Error
      return false
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